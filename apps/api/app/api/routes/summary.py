"""
Daily Memory Summary router.

Endpoint
--------
GET /summary/daily?date=YYYY-MM-DD

Returns a rule-based summary of one day's activity.
No LLM, no API key, no external services.

Response shape:
    date              str
    total_memories    int
    total_sessions    int
    main_apps         [{app, count}]
    key_topics        [str]
    work_summary      str   — one natural-language paragraph
    timeline_summary  [{session_id, title, start_time, end_time,
                        duration_str, memory_count, keywords}]
    topic_clusters    [{label, keywords, memory_ids, count}]
"""

import logging
import re
from collections import Counter
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.services.memory_store import memory_store
from app.services.session_service import NOISE_WORDS, detect_sessions, _format_duration
from app.services.topic_service import cluster_memories

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/summary", tags=["summary"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _filter_by_date(items: list[dict], target: date) -> list[dict]:
    """Return only memories whose created_at (local) falls on target_date."""
    result = []
    for item in items:
        raw = item.get("created_at", "")
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt.astimezone().date() == target:
                result.append(item)
        except Exception:
            pass
    return result


def _top_apps(memories: list[dict], n: int = 5) -> list[dict]:
    counter: Counter = Counter()
    for m in memories:
        app = (m.get("metadata") or {}).get("app_name")
        if app:
            counter[app] += 1
    return [{"app": app, "count": cnt} for app, cnt in counter.most_common(n)]


def _key_topics(memories: list[dict], n: int = 10) -> list[str]:
    freq: dict[str, int] = {}
    for m in memories:
        for w in re.findall(r"\b[A-Za-z][a-zA-Z]{2,}\b", m.get("title", "")):
            wl = w.lower()
            if wl not in NOISE_WORDS:
                freq[wl] = freq.get(wl, 0) + 3
        text = m.get("text", "")
        if "[OCR" not in text:
            for w in re.findall(r"\b[A-Za-z][a-zA-Z]{3,}\b", text[:500]):
                wl = w.lower()
                if wl not in NOISE_WORDS:
                    freq[wl] = freq.get(wl, 0) + 1
    return [k for k, _ in sorted(freq.items(), key=lambda x: -x[1])[:n]]


def _work_summary(
    memories: list[dict],
    sessions: list[dict],
    target: date,
) -> str:
    if not memories:
        return f"No activity recorded on {target.strftime('%B %d, %Y')}."

    n      = len(memories)
    n_sess = len(sessions)
    parts  = [
        f"Captured {n} memor{'ies' if n != 1 else 'y'} across "
        f"{n_sess} work session{'s' if n_sess != 1 else ''} "
        f"on {target.strftime('%B %d')}."
    ]

    apps = _top_apps(memories, 3)
    if apps:
        names = [a["app"] for a in apps]
        parts.append(f"Primary apps: {', '.join(names)}.")

    topics = _key_topics(memories, 5)
    if topics:
        parts.append(f"Key topics: {', '.join(topics)}.")

    times: list[datetime] = []
    for m in memories:
        try:
            dt = datetime.fromisoformat(m.get("created_at", ""))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            times.append(dt.astimezone())
        except Exception:
            pass
    if times:
        first = min(times).strftime("%I:%M %p").lstrip("0")
        last  = max(times).strftime("%I:%M %p").lstrip("0")
        total_secs = sum(
            s.get("duration_secs", 0) for s in sessions
        )
        parts.append(
            f"Active from {first} to {last} "
            f"({_format_duration(total_secs)} total)."
        )

    return "  ".join(parts)


def _timeline(sessions: list[dict]) -> list[dict]:
    """Slim, chronologically ordered session list for the timeline field."""
    return [
        {
            "session_id":   s["session_id"],
            "title":        s["title"],
            "start_time":   s["start_time"],
            "end_time":     s["end_time"],
            "duration_str": s["duration_str"],
            "memory_count": s["memory_count"],
            "keywords":     s.get("keywords", [])[:4],
            "topics":       s.get("topics", []),
        }
        for s in sorted(sessions, key=lambda x: x["start_time"])
    ]


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.get("/daily")
async def daily_summary(
    date_str: str | None = Query(
        default=None,
        alias="date",
        description="Date in YYYY-MM-DD format. Defaults to today (local timezone).",
    ),
):
    """
    Rule-based daily activity summary.
    No LLM required.  All data is derived from stored memories and sessions.
    """
    if date_str is None:
        target = datetime.now().astimezone().date()
    else:
        try:
            target = date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date '{date_str}'. Expected YYYY-MM-DD.",
            )

    all_items  = memory_store.list()
    day_items  = _filter_by_date(all_items, target)
    sessions   = detect_sessions(day_items)

    topic_clusters = cluster_memories(day_items, n_topics=6)

    logger.info(
        "summary/daily %s: %d memories, %d sessions, %d clusters",
        target, len(day_items), len(sessions), len(topic_clusters),
    )

    return {
        "date":             target.isoformat(),
        "total_memories":   len(day_items),
        "total_sessions":   len(sessions),
        "main_apps":        _top_apps(day_items),
        "key_topics":       _key_topics(day_items),
        "work_summary":     _work_summary(day_items, sessions, target),
        "timeline_summary": _timeline(sessions),
        "topic_clusters":   topic_clusters,
    }
