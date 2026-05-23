"""
Hybrid memory search: keyword + semantic cosine + recency scoring.

When sentence-transformers is available:
    combined = 0.35 * kw_norm + 0.55 * sem_cosine + 0.10 * recency
    semantic threshold: 0.30 minimum cosine similarity

When unavailable (graceful fallback):
    combined = kw_raw (unchanged keyword behaviour)
"""

import logging
import re
from datetime import datetime, timezone

from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

_SEM_THRESHOLD = 0.30
_KW_WEIGHT  = 0.35
_SEM_WEIGHT = 0.55
_REC_WEIGHT = 0.10

# Deduplication: fingerprint on first N chars of OCR text
_DEDUP_CHARS = 80


# ---------------------------------------------------------------------------
# Keyword scoring
# ---------------------------------------------------------------------------

def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _phrase_in(phrase: str, field: str) -> bool:
    return phrase in field.lower()


def _kw_score(query: str, item: dict) -> int:
    """
    Additive keyword score:
        +8  exact phrase in title
        +6  exact phrase in text
        +5  exact phrase in app_name
        +4  exact phrase in original_filename or window_title
        +3  each query word in title
        +3  each query word in app_name
        +2  each query word in text
        +2  each query word matching a tag
        +2  each query word in window_title
        +1  query word in source
    """
    q = query.lower().strip()
    q_words = _words(q)

    title        = (item.get("title") or "").lower()
    text         = (item.get("text") or "").lower()
    source       = (item.get("source") or "").lower()
    tags         = [t.lower() for t in (item.get("tags") or [])]
    meta         = item.get("metadata") or {}
    orig_filename = meta.get("original_filename", "").lower()
    app_name     = (meta.get("app_name") or "").lower()
    window_title = (meta.get("window_title") or "").lower()

    score = 0
    if _phrase_in(q, title):
        score += 8
    if _phrase_in(q, text):
        score += 6
    if app_name and _phrase_in(q, app_name):
        score += 5
    if orig_filename and _phrase_in(q, orig_filename):
        score += 4
    if window_title and _phrase_in(q, window_title):
        score += 4
    for word in q_words:
        if word in title:
            score += 3
        if app_name and word in app_name:
            score += 3
        if word in text:
            score += 2
        if any(word in tag for tag in tags):
            score += 2
        if window_title and word in window_title:
            score += 2
        if word in source:
            score += 1
    return score


# ---------------------------------------------------------------------------
# Recency scoring
# ---------------------------------------------------------------------------

def _recency_score(item: dict) -> float:
    """Return a 0–1 score based on how recently the item was created."""
    created_at = item.get("created_at", "")
    if not created_at:
        return 0.10
    try:
        dt = datetime.fromisoformat(created_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_secs = (datetime.now(timezone.utc) - dt).total_seconds()
        if age_secs < 1800:       # < 30 min
            return 1.00
        if age_secs < 7200:       # < 2 h
            return 0.85
        if age_secs < 28800:      # < 8 h
            return 0.65
        if age_secs < 86400:      # < 24 h
            return 0.45
        if age_secs < 259200:     # < 72 h
            return 0.25
        return 0.10
    except (ValueError, OverflowError):
        return 0.10


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _deduplicate(results: list[dict]) -> list[dict]:
    """
    Remove near-duplicate results that share the same OCR-text fingerprint.
    Keeps the highest-scoring entry per fingerprint.
    Results must already be sorted by score descending.
    """
    seen: set[str] = set()
    out: list[dict] = []
    for r in results:
        text = (r["item"].get("text") or "").strip()
        # Non-OCR items (no text) are never considered duplicates
        if not text:
            out.append(r)
            continue
        fp = text[:_DEDUP_CHARS].lower()
        if fp not in seen:
            seen.add(fp)
            out.append(r)
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_memories(query: str, items: list[dict]) -> list[dict]:
    """
    Score and rank memory items against a query string.

    Returns list of:
        {
            "score":          float,   # combined (0–100 scale)
            "keyword_score":  float,   # raw keyword hits
            "semantic_score": float,   # cosine similarity (0–1)
            "item":           dict,
        }
    sorted by score descending, then created_at descending on ties.
    """
    q = query.strip()
    if not q:
        return []

    semantic_active = embedding_service.is_available()

    # Encode query once using the cached embed_query path
    query_vec: list[float] | None = None
    if semantic_active:
        query_vec = embedding_service.embed_query(q)

    # --- Keyword pass ---
    kw_scores: list[int] = [_kw_score(q, it) for it in items]
    max_kw = max((s for s in kw_scores if s > 0), default=1)

    results: list[dict] = []

    for item, kw_raw in zip(items, kw_scores):
        kw_norm = kw_raw / max_kw  # 0.0 – 1.0

        sem_score = 0.0
        if semantic_active and query_vec is not None:
            item_vec = item.get("embedding")
            if item_vec:
                sim = embedding_service.cosine_similarity(query_vec, item_vec)
                sem_score = max(0.0, float(sim))

        rec_score = _recency_score(item)

        # Decide inclusion
        if semantic_active:
            if kw_raw == 0 and sem_score < _SEM_THRESHOLD:
                continue  # neither signal — skip
            combined = round(
                (_KW_WEIGHT * kw_norm + _SEM_WEIGHT * sem_score + _REC_WEIGHT * rec_score) * 100,
                1,
            )
        else:
            if kw_raw == 0:
                continue
            combined = float(kw_raw)

        results.append({
            "score":          combined,
            "keyword_score":  float(kw_raw),
            "semantic_score": round(sem_score, 4),
            "recency_score":  round(rec_score, 2),
            "item":           item,
        })

    results.sort(
        key=lambda x: (x["score"], x["item"].get("created_at", "")),
        reverse=True,
    )
    results = _deduplicate(results)
    logger.debug(
        "search('%s'): %d candidates → %d after dedup  [semantic=%s]",
        q, len(items), len(results), semantic_active,
    )
    return results
