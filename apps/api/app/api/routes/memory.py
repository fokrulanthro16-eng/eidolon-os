import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.models.memory import (
    ChatRequest,
    ChatResponse,
    MemoryItem,
    MemorySearchRequest,
    MemorySearchResponse,
    MemorySearchResult,
)
from app.services.chat_memory_service import chat_recall
from app.services.pdf_chunk_service import invalidate_cache as invalidate_pdf_cache
from app.services.embedding_service import embedding_service
from app.services.memory_store import memory_store
from app.services.ocr_service import extract_text_from_image
from app.services.pdf_service import extract_text_from_pdf
from app.services.search_service import search_memories
from app.services.storage_service import (
    delete_file,
    get_image_metadata,
    save_audio_file,
    save_pdf_file,
    save_upload_file,
)
from app.utils.ids import create_memory_id
from app.utils.time import utc_now_iso

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/memory", tags=["memory"])


@router.post("/ingest-image", status_code=status.HTTP_201_CREATED)
async def ingest_image(
    file: UploadFile = File(...),
    source_app: str | None = Form(None),
    window_title: str | None = Form(None),
):
    """
    Ingest an image into OmniMemory.

    Pipeline:
        validate → save → OCR → metadata → embed → persist → return
    """
    memory_id = create_memory_id()
    now = utc_now_iso()

    saved_path = await save_upload_file(file=file, memory_id=memory_id)
    img_meta = get_image_metadata(saved_path)
    ocr = extract_text_from_image(saved_path)

    original_name = file.filename or "upload"
    title = window_title or original_name

    tags = [source_app] if source_app else []

    # Vision scene analysis (heuristic, non-fatal)
    try:
        from app.services.vision_service import analyze_screenshot
        vision = analyze_screenshot(ocr["text"], source_app, saved_path)
    except Exception:
        vision = {}

    item = MemoryItem(
        id=memory_id,
        type="image",
        title=title,
        text=ocr["text"],
        file_path=str(saved_path),
        source=source_app or "manual_upload",
        tags=tags,
        metadata={
            "original_filename": original_name,
            "ocr_engine":        ocr["engine"],
            "ocr_available":     ocr["available"],
            "ocr_confidence":    ocr.get("confidence", -1.0),
            "width":             img_meta["width"],
            "height":            img_meta["height"],
            "file_size":         img_meta["file_size"],
            "app_name":          source_app,
            "window_title":      window_title,
            "exe_name":          None,
            # Vision intelligence
            "scene_type":        vision.get("scene_type", "unknown"),
            "workflow_type":     vision.get("workflow_type", "other"),
            "ui_layout":         vision.get("ui_layout", "unknown"),
            "visual_tags":       vision.get("visual_tags", []),
        },
        created_at=now,
        updated_at=now,
    )

    item_dict = item.model_dump()

    # Semantic embedding — non-fatal
    embedding = embedding_service.embed_for_storage(title, ocr["text"])
    if embedding is not None:
        item_dict["embedding"] = embedding

    saved = memory_store.add(item_dict)
    logger.info("Ingested image %s — OCR: %s  embedding: %s", memory_id, ocr["engine"], embedding is not None)

    return {"success": True, "memory": saved}


@router.post("/ingest-pdf", status_code=status.HTTP_201_CREATED)
async def ingest_pdf(file: UploadFile = File(...)):
    """
    Ingest a PDF document into OmniMemory.

    Pipeline:
        validate → save → extract text (PyMuPDF) → embed → persist → return

    If PyMuPDF is not installed the PDF is still stored and retrievable;
    text search and semantic search will not work until PyMuPDF is installed.
    Scanned-page OCR is attempted automatically if Tesseract is also available.
    """
    memory_id = create_memory_id()
    now = utc_now_iso()

    saved_path = await save_pdf_file(file=file, memory_id=memory_id)
    original_name = file.filename or "document.pdf"
    file_size = saved_path.stat().st_size

    pdf = extract_text_from_pdf(saved_path)

    # Title: original filename without path
    title = original_name

    item = MemoryItem(
        id=memory_id,
        type="pdf",
        title=title,
        text=pdf["text"],
        file_path=str(saved_path),
        source="pdf_upload",
        tags=["pdf"],
        metadata={
            "original_filename":     original_name,
            "file_size":             file_size,
            "page_count":            pdf["page_count"],
            "pages_extracted":       pdf["pages_extracted"],
            "scanned_pages":         pdf["scanned_pages"],
            "extraction_engine":     pdf["extraction_engine"],
            "extraction_available":  pdf["extraction_available"],
        },
        created_at=now,
        updated_at=now,
    )

    item_dict = item.model_dump()

    # Embed title + first 800 chars of extracted text for semantic search
    embed_text = pdf["text"][:800] if pdf["extraction_available"] else ""
    embedding = embedding_service.embed_for_storage(title, embed_text)
    if embedding is not None:
        item_dict["embedding"] = embedding

    saved = memory_store.add(item_dict)
    logger.info(
        "Ingested PDF %s — pages: %d  engine: %s  embedding: %s",
        memory_id, pdf["page_count"], pdf["extraction_engine"], embedding is not None,
    )

    return {"success": True, "memory": saved}


@router.post("/ingest-audio", status_code=status.HTTP_201_CREATED)
async def ingest_audio(file: UploadFile = File(...)):
    """
    Ingest an audio file into OmniMemory.

    Pipeline:
        validate → save → transcribe (Whisper if available) → embed → persist → return

    Accepted formats: .mp3 .wav .m4a .ogg .flac .webm
    Transcription requires faster-whisper (pip install faster-whisper).
    The file is stored regardless; transcript is added when Whisper is available.
    """
    from app.services.voice_service import transcribe_audio, format_duration

    memory_id = create_memory_id()
    now = utc_now_iso()

    saved_path = await save_audio_file(file=file, memory_id=memory_id)
    original_name = file.filename or "recording.mp3"

    transcript = transcribe_audio(saved_path)
    title = original_name

    item = MemoryItem(
        id=memory_id,
        type="voice",
        title=title,
        text=transcript["text"],
        file_path=str(saved_path),
        source="voice_upload",
        tags=["voice"],
        metadata={
            "original_filename":     original_name,
            "file_size":             saved_path.stat().st_size,
            "language":              transcript["language"],
            "duration_secs":         transcript["duration_secs"],
            "duration_str":          format_duration(transcript["duration_secs"]),
            "transcript_confidence": transcript["transcript_confidence"],
            "transcription_engine":  "faster-whisper" if transcript["available"] else "fallback",
            "transcription_available": transcript["available"],
        },
        created_at=now,
        updated_at=now,
    )

    item_dict = item.model_dump()

    embed_text = transcript["text"][:800] if transcript["available"] else ""
    embedding = embedding_service.embed_for_storage(title, embed_text)
    if embedding is not None:
        item_dict["embedding"] = embedding

    saved = memory_store.add(item_dict)
    logger.info(
        "Ingested audio %s — lang: %s  duration: %.1fs  embedding: %s",
        memory_id, transcript["language"], transcript["duration_secs"], embedding is not None,
    )

    return {"success": True, "memory": saved}


@router.get("/list")
async def list_memory():
    """Return all memory items, oldest first."""
    items = memory_store.list()
    return {"count": len(items), "items": items}


@router.get("/timeline")
async def memory_timeline():
    """Return all memory items sorted newest first."""
    items = sorted(
        memory_store.list(),
        key=lambda x: x.get("created_at", ""),
        reverse=True,
    )
    return {"count": len(items), "items": items}


@router.post("/search", response_model=MemorySearchResponse)
async def search_memory(body: MemorySearchRequest):
    """
    Score all memory items against query using hybrid keyword + semantic search.
    Returns results sorted by score descending.
    """
    all_items = memory_store.list()
    raw_results = search_memories(query=body.query, items=all_items)

    results = [
        MemorySearchResult(
            score=r["score"],
            keyword_score=r["keyword_score"],
            semantic_score=r["semantic_score"],
            item=MemoryItem(**{k: v for k, v in r["item"].items() if k != "embedding"}),
        )
        for r in raw_results
    ]

    return MemorySearchResponse(
        query=body.query,
        count=len(results),
        results=results,
        semantic_mode=embedding_service.is_available(),
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_memory(body: ChatRequest):
    """
    Natural language memory recall with optional LLM synthesis.
    """
    result = chat_recall(message=body.message)

    matches = [
        MemorySearchResult(
            score=r["score"],
            keyword_score=r.get("keyword_score", 0.0),
            semantic_score=r.get("semantic_score", 0.0),
            item=MemoryItem(**{k: v for k, v in r["item"].items() if k != "embedding"}),
        )
        for r in result["matches"]
    ]

    return ChatResponse(
        answer=result["answer"],
        matches=matches,
        count=result["count"],
        query_used=result["query_used"],
        brain_mode=result.get("brain_mode", "rule_based"),
    )


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a memory item and its associated file."""
    item = memory_store.get(memory_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found.")

    delete_file(item.get("file_path"))
    memory_store.delete(memory_id)
    invalidate_pdf_cache(memory_id)
    logger.info("Deleted memory %s", memory_id)

    return {"success": True, "deleted_id": memory_id}
