"""
PDF chat service — rule-based answer synthesis from PDF chunk matches.

No LLM. No API key. No hallucination.
All answers are grounded solely in matched chunk text.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_TOP_K        = 5     # chunks to retrieve per question
_MIN_SCORE    = 0.10  # discard chunks below this relevance threshold
_ANSWER_CHARS = 800   # max characters in the synthesised answer string


# ---------------------------------------------------------------------------
# Synthesis helpers
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _build_answer(top_chunks: list[dict]) -> tuple[str, float]:
    """
    Concatenate the best-matching chunks into a readable answer string.
    Returns (answer_text, confidence_0_to_1).
    """
    if not top_chunks:
        return "I could not find enough PDF context to answer that question.", 0.0

    best = top_chunks[0]["score"]

    if best < 0.15:
        return (
            "The PDF(s) don't appear to contain information directly related to "
            "your question. Try rephrasing or ask about a different topic.",
            round(best, 3),
        )

    seen: set[str] = set()
    snippets: list[str] = []
    total = 0

    for chunk in top_chunks:
        cleaned = _clean(chunk["text"])
        key = cleaned[:60]
        if key in seen:
            continue
        seen.add(key)
        remaining = _ANSWER_CHARS - total
        if remaining <= 0:
            break
        snippet = cleaned[:remaining]
        snippets.append(snippet)
        total += len(snippet)

    answer = " … ".join(snippets)
    if total >= _ANSWER_CHARS:
        answer += "…"

    confidence = min(round(best * 1.2, 3), 1.0)
    return answer, confidence


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def answer_pdf_question(
    question: str,
    pdf_memory_id: str | None = None,
) -> dict[str, Any]:
    """
    Answer a question from stored PDF content.

    Parameters
    ----------
    question      : user's question string
    pdf_memory_id : if given, search only that PDF; otherwise search all PDFs

    Returns
    -------
    {answer, pdf_title, matched_chunks, confidence, source_pages}
    """
    from app.services.memory_store import memory_store
    from app.services.pdf_chunk_service import get_chunks, retrieve_chunks

    all_items = memory_store.list()
    pdf_items = [
        it for it in all_items
        if it.get("type") == "pdf"
        and (it.get("metadata") or {}).get("extraction_available", False)
    ]

    if pdf_memory_id:
        pdf_items = [it for it in pdf_items if it["id"] == pdf_memory_id]

    if not pdf_items:
        msg = (
            "PDF not found or its text has not been extracted yet."
            if pdf_memory_id
            else "No PDFs with extractable text are stored yet. Upload a PDF first."
        )
        return {
            "answer":         msg,
            "pdf_title":      None,
            "matched_chunks": [],
            "confidence":     0.0,
            "source_pages":   [],
        }

    # Collect all chunks from candidate PDFs
    all_chunks: list[dict] = []
    pdf_titles: dict[str, str] = {}

    for item in pdf_items:
        text = item.get("text", "")
        if not text or text.startswith("[PDF stored"):
            continue
        pdf_titles[item["id"]] = item.get("title", item["id"])
        all_chunks.extend(get_chunks(item["id"], text))

    if not all_chunks:
        return {
            "answer":         "I could not find enough PDF context to answer that question.",
            "pdf_title":      None,
            "matched_chunks": [],
            "confidence":     0.0,
            "source_pages":   [],
        }

    top = retrieve_chunks(question, all_chunks, top_k=_TOP_K)
    top = [c for c in top if c["score"] >= _MIN_SCORE]

    answer, confidence = _build_answer(top)

    source_pages = sorted({c["page_num"] for c in top if c.get("page_num")})

    primary_mid = top[0]["memory_id"] if top else None
    pdf_title   = pdf_titles.get(primary_mid) if primary_mid else None

    serialised = [
        {
            "chunk_id":  c["chunk_id"],
            "memory_id": c["memory_id"],
            "page_num":  c["page_num"],
            "text":      _clean(c["text"])[:400],
            "score":     round(c["score"], 4),
        }
        for c in top
    ]

    logger.info(
        "PDF chat: %d chunks matched, confidence %.2f, pages %s",
        len(top), confidence, source_pages,
    )

    return {
        "answer":         answer,
        "pdf_title":      pdf_title,
        "matched_chunks": serialised,
        "confidence":     confidence,
        "source_pages":   source_pages,
    }
