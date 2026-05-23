"""
Memory ingestion pipeline orchestrator.

Full flow:
  Input → Preprocess → PaddleOCR → Qwen2-VL → Chunk → BGE-M3 → pgvector + PostgreSQL

Async at orchestration level; CPU-heavy ops (OCR, embed) via asyncio.to_thread().
Qwen2-VL is optional — controlled by settings.vl_enabled.
"""
import asyncio
import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.db.models import CaptureEvent, MemoryRecord
from apps.api.engines.memory.chunker import chunk_text
from apps.api.engines.memory.embedder import get_embedder
from apps.api.engines.memory.vector_store import upsert_chunks
from apps.api.engines.memory.vision.qwen_vl import analyze_screenshot

logger = logging.getLogger(__name__)

SourceType = Literal["screenshot", "upload", "clipboard", "note"]


def _compute_file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_thumbnail(image: Image.Image, save_dir: Path, record_id: str) -> str:
    thumb = image.copy()
    thumb.thumbnail((480, 270), Image.LANCZOS)
    thumb_path = save_dir / f"{record_id}_thumb.webp"
    thumb.save(thumb_path, "WEBP", quality=75)
    return str(thumb_path)


async def ingest_image(
    image: Image.Image,
    db: AsyncSession,
    source_type: SourceType = "screenshot",
    source_path: str | None = None,
    source_app: str | None = None,
    window_title: str | None = None,
    file_hash: str | None = None,
) -> MemoryRecord:
    from apps.api.config import settings
    from apps.api.engines.memory.ocr.paddle_ocr import get_ocr_engine

    start = time.monotonic()
    record_id = str(uuid.uuid4())

    # OCR (CPU-heavy → thread pool)
    ocr_result = await asyncio.to_thread(get_ocr_engine().read_image, image)

    # Visual context from Qwen2-VL (async REST, no thread needed)
    visual_summary = await analyze_screenshot(image)

    # Thumbnail generation (I/O → thread pool)
    thumb_path = await asyncio.to_thread(
        _make_thumbnail, image, settings.thumbnails_dir, record_id
    )

    # Chunk extracted text
    text_to_chunk = ocr_result.raw_text or ""
    if visual_summary:
        # Prepend VL summary as a high-signal chunk for retrieval
        text_to_chunk = f"{visual_summary}\n\n{text_to_chunk}"

    chunks = chunk_text(text_to_chunk) if text_to_chunk.strip() else []

    # Embed all chunks (CPU-heavy → thread pool)
    embeddings: list[list[float]] = []
    if chunks:
        embeddings = await asyncio.to_thread(
            get_embedder().embed_passages, chunks
        )

    # Write vectors to pgvector
    if chunks:
        await upsert_chunks(
            record_id=record_id,
            chunks=chunks,
            embeddings=embeddings,
            source_type=source_type,
            source_app=source_app,
            window_title=window_title,
        )

    # Persist metadata to PostgreSQL
    record = MemoryRecord(
        id=record_id,
        source_type=source_type,
        source_path=source_path,
        source_app=source_app,
        window_title=window_title,
        raw_text=ocr_result.raw_text or None,
        visual_summary=visual_summary,
        file_hash=file_hash,
        chunk_count=len(chunks),
        ocr_confidence=ocr_result.mean_confidence or None,
        thumbnail_path=thumb_path,
    )
    db.add(record)

    duration_ms = int((time.monotonic() - start) * 1000)
    db.add(CaptureEvent(
        memory_record_id=record_id,
        success=True,
        duration_ms=duration_ms,
        source_app=source_app,
        window_title=window_title,
    ))
    await db.flush()

    logger.info(
        "Ingested %s | type=%s | chunks=%d | ocr_conf=%.2f | vl=%s | %dms",
        record_id, source_type, len(chunks),
        ocr_result.mean_confidence, "yes" if visual_summary else "no", duration_ms,
    )
    return record


async def ingest_text(
    text: str,
    db: AsyncSession,
    source_type: SourceType = "note",
    source_app: str | None = None,
    window_title: str | None = None,
) -> MemoryRecord:
    record_id = str(uuid.uuid4())

    chunks = chunk_text(text)
    embeddings: list[list[float]] = []
    if chunks:
        embeddings = await asyncio.to_thread(
            get_embedder().embed_passages, chunks
        )
        await upsert_chunks(
            record_id=record_id,
            chunks=chunks,
            embeddings=embeddings,
            source_type=source_type,
            source_app=source_app,
            window_title=window_title,
        )

    record = MemoryRecord(
        id=record_id,
        source_type=source_type,
        source_app=source_app,
        window_title=window_title,
        raw_text=text,
        chunk_count=len(chunks),
    )
    db.add(record)
    await db.flush()
    return record
