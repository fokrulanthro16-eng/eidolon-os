"""
PDF routes — Phase 8: PDF Chat Mode.

POST /pdf/chat   Answer a question from stored PDF content
GET  /pdf/list   List PDFs available for chat (with extraction status)
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.memory_store import memory_store
from app.services.pdf_chat_service import answer_pdf_question

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pdf", tags=["pdf"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class PdfChatRequest(BaseModel):
    question:      str       = Field(min_length=1, max_length=500)
    pdf_memory_id: str | None = None


class PdfChunk(BaseModel):
    chunk_id:  str
    memory_id: str
    page_num:  int
    text:      str
    score:     float


class PdfChatResponse(BaseModel):
    answer:         str
    pdf_title:      str | None
    matched_chunks: list[PdfChunk]
    confidence:     float
    source_pages:   list[int]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=PdfChatResponse)
async def pdf_chat(body: PdfChatRequest):
    """Answer a question grounded in stored PDF content. No LLM required."""
    result = answer_pdf_question(
        question=body.question,
        pdf_memory_id=body.pdf_memory_id,
    )
    return PdfChatResponse(
        answer=result["answer"],
        pdf_title=result["pdf_title"],
        matched_chunks=[PdfChunk(**c) for c in result["matched_chunks"]],
        confidence=result["confidence"],
        source_pages=result["source_pages"],
    )


@router.get("/list")
async def list_pdfs():
    """List all PDFs stored in memory with their extraction status."""
    items = memory_store.list()
    pdfs = [
        {
            "memory_id":            it["id"],
            "title":                it.get("title", it["id"]),
            "page_count":           (it.get("metadata") or {}).get("page_count", 0),
            "extraction_available": (it.get("metadata") or {}).get("extraction_available", False),
            "created_at":           it.get("created_at", ""),
        }
        for it in items
        if it.get("type") == "pdf"
    ]
    pdfs.sort(key=lambda p: p["created_at"], reverse=True)
    return {"count": len(pdfs), "pdfs": pdfs}


@router.get("/{memory_id}/summary")
async def pdf_summary(memory_id: str):
    """
    Return a lightweight summary of a stored PDF:
      - first ~500 chars of extracted text as abstract
      - top keywords
      - page / extraction metadata
    """
    import re
    from fastapi import HTTPException
    from app.services.session_service import NOISE_WORDS
    from collections import Counter

    item = memory_store.get(memory_id)
    if item is None or item.get("type") != "pdf":
        raise HTTPException(status_code=404, detail=f"PDF memory '{memory_id}' not found.")

    text  = item.get("text", "")
    meta  = item.get("metadata") or {}

    # Abstract: first non-header paragraph
    abstract = ""
    if meta.get("extraction_available") and text and not text.startswith("[PDF stored"):
        # Strip [Page N] markers for the abstract
        clean = re.sub(r"\[Page \d+\]\s*", "", text)
        abstract = " ".join(clean.split())[:500]

    # Keywords: top content words
    freq: Counter = Counter()
    for word in re.findall(r"[a-zA-Z]{4,}", text.lower()):
        if word not in NOISE_WORDS:
            freq[word] += 1
    top_keywords = [w for w, _ in freq.most_common(10)]

    return {
        "memory_id":            memory_id,
        "title":                item.get("title", memory_id),
        "abstract":             abstract or "[Text not extracted — install PyMuPDF]",
        "top_keywords":         top_keywords,
        "page_count":           meta.get("page_count", 0),
        "pages_extracted":      meta.get("pages_extracted", 0),
        "extraction_available": meta.get("extraction_available", False),
        "extraction_engine":    meta.get("extraction_engine", "unknown"),
        "created_at":           item.get("created_at", ""),
    }


@router.get("/related/{memory_id}")
async def related_pdfs(memory_id: str, top_k: int = 3):
    """
    Return PDFs most similar to the given PDF.
    Uses cosine similarity on stored embeddings when available;
    falls back to keyword overlap.
    """
    import re
    from fastapi import HTTPException
    from app.services.embedding_service import embedding_service
    from app.services.session_service import NOISE_WORDS
    from collections import Counter

    source = memory_store.get(memory_id)
    if source is None or source.get("type") != "pdf":
        raise HTTPException(status_code=404, detail=f"PDF memory '{memory_id}' not found.")

    all_items = memory_store.list()
    candidates = [it for it in all_items if it.get("type") == "pdf" and it["id"] != memory_id]

    if not candidates:
        return {"memory_id": memory_id, "related": []}

    source_emb = source.get("embedding")
    scored = []

    if source_emb and embedding_service.is_available():
        for c in candidates:
            c_emb = c.get("embedding")
            if c_emb:
                sim = embedding_service.cosine_similarity(source_emb, c_emb)
                scored.append((sim, c))
        scored.sort(key=lambda x: x[0], reverse=True)
    else:
        # Keyword overlap fallback
        def _kws(item: dict) -> set[str]:
            text = item.get("title", "") + " " + item.get("text", "")[:600]
            return {w for w in re.findall(r"[a-zA-Z]{4,}", text.lower()) if w not in NOISE_WORDS}

        src_kws = _kws(source)
        for c in candidates:
            c_kws = _kws(c)
            if src_kws and c_kws:
                overlap = len(src_kws & c_kws) / len(src_kws | c_kws)
                scored.append((overlap, c))
        scored.sort(key=lambda x: x[0], reverse=True)

    related = [
        {
            "memory_id":  c["id"],
            "title":      c.get("title", c["id"]),
            "score":      round(score, 4),
            "page_count": (c.get("metadata") or {}).get("page_count", 0),
        }
        for score, c in scored[:top_k]
        if score > 0.05
    ]

    return {"memory_id": memory_id, "related": related}
