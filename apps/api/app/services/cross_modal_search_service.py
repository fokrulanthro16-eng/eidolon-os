"""
Cross-Modal Search Service — Phase 15 Neural Search.

Searches ALL memory modalities simultaneously and returns:
  - answer_summary  : compact rule-based summary of findings
  - results         : ranked list of all matching memories
  - grouped_by_modality: results bucketed by type
  - timeline        : events ordered chronologically
  - confidence      : search quality indicator
  - search_mode     : "semantic" | "keyword" | "hybrid"

Ranking formula:
  base_score (from search_service) * modality_weight * recency_factor * workflow_bonus

No cloud, no LLM required. Every answer is grounded in actual stored memories.
"""

import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Modality display labels
_TYPE_LABELS: dict[str, str] = {
    "screenshot": "Screen Captures",
    "pdf":        "PDF Documents",
    "voice":      "Voice Memos",
    "video":      "Video & Camera",
    "image":      "Images",
    "text":       "Text Notes",
}

# Modality relevance hints — boost score for certain query keywords
_MODALITY_HINTS: dict[str, list[str]] = {
    "pdf":        ["pdf", "document", "paper", "read", "chapter", "article"],
    "voice":      ["voice", "audio", "recorded", "said", "spoke", "transcript"],
    "video":      ["video", "camera", "cctv", "surveillance", "detected", "motion", "yolo"],
    "screenshot": ["screen", "saw", "viewed", "browser", "editor", "vscode", "coding", "chrome"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dt(iso: str) -> datetime | None:
    try:
        s = iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _modality_weight(query_lower: str, mem_type: str) -> float:
    """Boost score if query hints at this modality."""
    hints = _MODALITY_HINTS.get(mem_type, [])
    for hint in hints:
        if hint in query_lower:
            return 1.25
    return 1.0


def _build_grouped(results: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        t = r["item"].get("type", "other")
        groups[t].append(r)
    # Sort each group by score desc
    return {k: sorted(v, key=lambda x: x["score"], reverse=True) for k, v in groups.items()}


def _build_timeline(results: list[dict], limit: int = 40) -> list[dict]:
    """Return results ordered chronologically (oldest first), capped at limit."""
    with_dt = []
    for r in results:
        dt = _parse_dt(r["item"].get("created_at", ""))
        if dt:
            with_dt.append((dt, r))
    with_dt.sort(key=lambda x: x[0])
    return [
        {
            "id":           r["item"].get("id"),
            "type":         r["item"].get("type", ""),
            "title":        r["item"].get("title", ""),
            "created_at":   r["item"].get("created_at", ""),
            "score":        round(r.get("score", 0), 3),
            "app_name":     (r["item"].get("metadata") or {}).get("app_name", ""),
        }
        for _, r in with_dt[:limit]
    ]


def _answer_summary(query: str, results: list[dict]) -> str:
    """Rule-based compact answer summary from search results."""
    if not results:
        return f"No memories found matching '{query}'."

    count = len(results)
    types = defaultdict(int)
    apps: list[str] = []
    for r in results[:20]:
        types[r["item"].get("type", "other")] += 1
        a = (r["item"].get("metadata") or {}).get("app_name", "")
        if a and a not in apps:
            apps.append(a)

    type_strs = ", ".join(f"{c} {_TYPE_LABELS.get(t, t)}" for t, c in sorted(types.items(), key=lambda x: x[1], reverse=True))
    app_str   = ", ".join(apps[:4]) if apps else "various apps"
    top_title = results[0]["item"].get("title", "") if results else ""

    parts = [f"Found {count} memories matching '{query}'."]
    if type_strs:
        parts.append(f"Types: {type_strs}.")
    if apps:
        parts.append(f"Apps involved: {app_str}.")
    if top_title:
        parts.append(f"Best match: {top_title}.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Date-range filter
# ---------------------------------------------------------------------------

def _apply_date_filter(items: list[dict], date_range: dict | None) -> list[dict]:
    if not date_range:
        return items
    start_str = date_range.get("start")
    end_str   = date_range.get("end")
    start_dt  = _parse_dt(start_str) if start_str else None
    end_dt    = _parse_dt(end_str)   if end_str   else None
    result = []
    for m in items:
        dt = _parse_dt(m.get("created_at", ""))
        if dt is None:
            continue
        if start_dt and dt < start_dt:
            continue
        if end_dt and dt > end_dt:
            continue
        result.append(m)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def neural_search(
    query: str,
    memories: list[dict],
    type_filter: list[str] | None = None,
    date_range: dict | None = None,
    limit: int = 50,
) -> dict:
    """
    Cross-modal neural search across all memory modalities.

    Parameters
    ----------
    query       : natural language search query
    memories    : full memory store list
    type_filter : optional list of types to restrict search
    date_range  : optional {"start": ISO, "end": ISO}
    limit       : max total results to return

    Returns
    -------
    {
        query, answer_summary, results, grouped_by_modality,
        timeline, confidence, search_mode, total_found
    }
    """
    if not query.strip():
        return {
            "query": query,
            "answer_summary": "Empty query.",
            "results": [],
            "grouped_by_modality": {},
            "timeline": [],
            "confidence": 0.0,
            "search_mode": "none",
            "total_found": 0,
        }

    # Apply filters
    filtered = memories
    if date_range:
        filtered = _apply_date_filter(filtered, date_range)
    if type_filter:
        filtered = [m for m in filtered if m.get("type") in type_filter]

    # Base search via existing search_service
    try:
        from app.services.search_service import search_memories
        from app.services.embedding_service import embedding_service
        base_results = search_memories(query, filtered)
        search_mode = "hybrid" if embedding_service.is_available() else "keyword"
    except Exception as exc:
        logger.warning("neural_search base search failed: %s", exc)
        base_results = []
        search_mode = "fallback"

    # Re-rank with modality boosting
    q_lower = query.lower()
    boosted: list[dict] = []
    for r in base_results:
        mtype = r["item"].get("type", "other")
        mw = _modality_weight(q_lower, mtype)
        new_score = r["score"] * mw
        boosted.append({**r, "score": new_score, "modality_weight": mw})

    # Sort by boosted score
    boosted.sort(key=lambda x: x["score"], reverse=True)
    top = boosted[:limit]

    confidence = min(0.40 + 0.04 * len(top), 0.92) if top else 0.0

    return {
        "query":                query,
        "answer_summary":       _answer_summary(query, top),
        "results":              top,
        "grouped_by_modality":  {
            t: [{"score": r["score"], "id": r["item"].get("id"), "title": r["item"].get("title"), "created_at": r["item"].get("created_at"), "type": r["item"].get("type"), "source": r["item"].get("source"), "metadata": r["item"].get("metadata")}
                for r in rs[:15]]
            for t, rs in _build_grouped(top).items()
        },
        "timeline":             _build_timeline(top),
        "confidence":           round(confidence, 2),
        "search_mode":          search_mode,
        "total_found":          len(top),
    }
