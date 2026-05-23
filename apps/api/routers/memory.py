import io
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.db.database import get_db
from apps.api.db.models import MemoryRecord
from apps.api.engines.memory.ingestion import ingest_image, ingest_text
from apps.api.engines.memory.vector_store import delete_record_vectors, semantic_search
from apps.api.engines.memory.embedder import get_embedder
from apps.api.models.schemas import (
    IngestResponse,
    IngestTextRequest,
    SearchRequest,
    SearchResponse,
    SearchResult,
    TimelineEntry,
    TimelineResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


@router.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    source_app: str | None = Form(None),
    window_title: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files supported in Phase 1.")

    raw = await file.read()
    try:
        image = Image.open(io.BytesIO(raw))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file.")

    record = await ingest_image(
        image=image, db=db, source_type="upload",
        source_path=file.filename, source_app=source_app, window_title=window_title,
    )
    return IngestResponse(
        record_id=record.id, chunk_count=record.chunk_count,
        ocr_confidence=record.ocr_confidence, message="Ingested successfully.",
    )


@router.post("/ingest/text", response_model=IngestResponse)
async def ingest_text_endpoint(body: IngestTextRequest, db: AsyncSession = Depends(get_db)):
    record = await ingest_text(
        text=body.text, db=db, source_type=body.source_type,
        source_app=body.source_app, window_title=body.window_title,
    )
    return IngestResponse(
        record_id=record.id, chunk_count=record.chunk_count,
        ocr_confidence=None, message="Text ingested.",
    )


@router.post("/search", response_model=SearchResponse)
async def search_memory(body: SearchRequest, db: AsyncSession = Depends(get_db)):
    import asyncio
    query_vec = await asyncio.to_thread(get_embedder().embed_query, body.query)

    raw_results = await semantic_search(
        query_embedding=query_vec,
        top_k=body.top_k,
        source_type=body.source_type,
        date_from=body.date_from.isoformat() if body.date_from else None,
        date_to=body.date_to.isoformat() if body.date_to else None,
    )

    results = [
        SearchResult(
            record_id=r["record_id"],
            chunk_text=r["chunk_text"],
            score=float(r["score"]),
            source_type=r.get("source_type", "unknown"),
            source_app=r.get("source_app") or None,
            window_title=r.get("window_title") or None,
            visual_summary=r.get("visual_summary") or None,
            created_at=r["created_at"],
            thumbnail_path=r.get("thumbnail_path"),
        )
        for r in raw_results
    ]
    return SearchResponse(query=body.query, results=results, total=len(results))


@router.get("/timeline", response_model=TimelineResponse)
async def get_timeline(page: int = 1, page_size: int = 20, db: AsyncSession = Depends(get_db)):
    offset = (page - 1) * page_size
    stmt = (
        select(MemoryRecord)
        .order_by(MemoryRecord.created_at.desc())
        .offset(offset).limit(page_size)
    )
    records = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(select(func.count()).select_from(MemoryRecord))).scalar_one()

    entries = [
        TimelineEntry(
            id=r.id, created_at=r.created_at, source_type=r.source_type,
            source_app=r.source_app, window_title=r.window_title,
            raw_text_preview=(r.raw_text or "")[:200] or None,
            visual_summary=r.visual_summary, chunk_count=r.chunk_count,
            thumbnail_path=r.thumbnail_path,
        )
        for r in records
    ]
    return TimelineResponse(entries=entries, total=total, page=page, page_size=page_size)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(record_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(MemoryRecord).where(MemoryRecord.id == record_id)
    record = (await db.execute(stmt)).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found.")

    await delete_record_vectors(record_id)
    await db.delete(record)
    return JSONResponse(status_code=204, content=None)
