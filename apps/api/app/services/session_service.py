"""
Session detection service.

Groups memory items into work sessions by time gap.
Sessions are computed dynamically from timestamps — no stored state,
no schema migration needed for existing memories.

Default gap: 15 minutes between consecutive memories triggers a new session.
"""

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

_GAP_MINUTES = 15

# Exported so other modules (summary, topic service) can reuse without duplication
NOISE_WORDS = frozenset(
    "file edit view help window terminal code format tools settings "
    "explorer source control extensions ocr unavailable image stored "
    "successfully engine configured yet run start stop build debug "
    "test open close new save copy paste undo redo find replace "
    "screen capture the and for with from that this are was were "
    "has have had been will would could should".split()
)

_NOISE = NOISE_WORDS  # internal alias keeps existing references working


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_utc(iso: str) -> datetime | None:
    try:
        t = datetime.fromisoformat(iso)
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return "< 1 min"
    if seconds < 3600:
        m = int(seconds / 60)
        return f"{m} min{'s' if m != 1 else ''}"
    h = int(seconds / 3600)
    m = int((seconds % 3600) / 60)
    return f"{h}h {m}m" if m else f"{h}h"


def _extract_keywords(items: list[dict], n: int = 8) -> list[str]:
    """
    Frequency-rank words from titles (weight 3) and OCR text (weight 1).
    Skips noise words and OCR fallback placeholders.
    """
    freq: dict[str, int] = {}
    for item in items:
        for word in re.findall(r"\b[A-Za-z][a-zA-Z]{2,}\b", item.get("title", "")):
            wl = word.lower()
            if wl not in _NOISE:
                freq[wl] = freq.get(wl, 0) + 3

        text = item.get("text", "")
        if "[OCR" not in text:
            for word in re.findall(r"\b[A-Za-z][a-zA-Z]{3,}\b", text):
                wl = word.lower()
                if wl not in _NOISE:
                    freq[wl] = freq.get(wl, 0) + 1

    return [k for k, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:n]]


def _session_title(start_time: datetime, index: int, total: int) -> str:
    local = start_time.astimezone()
    hour = local.hour
    if hour < 6:
        period = "Night"
    elif hour < 12:
        period = "Morning"
    elif hour < 17:
        period = "Afternoon"
    elif hour < 21:
        period = "Evening"
    else:
        period = "Night"
    date_str = local.strftime("%b %d")
    return f"{period} Session · {date_str}"


def _extract_topics(items: list[dict], keywords: list[str]) -> list[str]:
    """
    Build a short topic list for a session from app names + top keywords.
    App names appear first; keywords fill remaining slots.
    """
    app_counter: Counter = Counter()
    for item in items:
        app = (item.get("metadata") or {}).get("app_name")
        if app:
            app_counter[app] += 1
    top_apps = [app for app, _ in app_counter.most_common(3)]
    seen_lower = {a.lower() for a in top_apps}
    extra = [kw for kw in keywords if kw.lower() not in seen_lower][:3]
    return (top_apps + extra)[:5]


def _build_summary(
    n: int,
    sources: list[str],
    keywords: list[str],
    duration_secs: float,
) -> str:
    count_str = f"{n} memor{'ies' if n != 1 else 'y'}"
    dur_str = _format_duration(duration_secs)
    parts = [f"{count_str} over {dur_str}"]
    if sources:
        src_str = ", ".join(sources[:3])
        if len(sources) > 3:
            src_str += f" +{len(sources) - 3}"
        parts.append(f"via {src_str}")
    summary = " · ".join(parts) + "."
    if keywords:
        summary += f" Topics: {', '.join(keywords[:5])}."
    return summary


def _assemble(items: list[dict], index: int, total: int) -> dict[str, Any]:
    """Build a complete session dict from a sorted list of memory items."""
    times = [_parse_utc(it.get("created_at", "")) for it in items]
    times = [t for t in times if t is not None]
    if not times:
        return {}

    start_time   = min(times)
    end_time     = max(times)
    duration_sec = (end_time - start_time).total_seconds()
    session_id   = "sess_" + start_time.strftime("%Y%m%d_%H%M%S")
    sources      = sorted({it.get("source", "") for it in items if it.get("source")})
    keywords     = _extract_keywords(items)

    topics = _extract_topics(items, keywords)

    return {
        "session_id":    session_id,
        "title":         _session_title(start_time, index, total),
        "start_time":    start_time.isoformat(),
        "end_time":      end_time.isoformat(),
        "duration_secs": int(duration_sec),
        "duration_str":  _format_duration(duration_sec),
        "memory_count":  len(items),
        "main_sources":  sources,
        "keywords":      keywords,
        "topics":        topics,
        "summary":       _build_summary(len(items), sources, keywords, duration_sec),
        "memories":      items,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_sessions(
    items: list[dict],
    gap_minutes: int = _GAP_MINUTES,
) -> list[dict]:
    """
    Group memory items into sessions.

    Returns sessions sorted newest-first.
    Each session dict contains a 'memories' key with the full item list,
    tagged with 'session_id' at the item level.
    """
    if not items:
        return []

    # Pair each item with its parsed timestamp; drop un-parseable
    pairs = [(it, _parse_utc(it.get("created_at", ""))) for it in items]
    pairs = [(it, t) for it, t in pairs if t is not None]
    pairs.sort(key=lambda x: x[1])

    threshold = gap_minutes * 60
    buckets: list[list[dict]] = []
    current: list[dict] = []
    last_t: datetime | None = None

    for item, t in pairs:
        if last_t is not None and (t - last_t).total_seconds() > threshold:
            if current:
                buckets.append(current)
            current = [item]
        else:
            current.append(item)
        last_t = t

    if current:
        buckets.append(current)

    total = len(buckets)
    sessions: list[dict] = []
    for i, bucket in enumerate(buckets):
        s = _assemble(bucket, i, total)
        if not s:
            continue
        # Tag each memory item with session_id
        sid = s["session_id"]
        for mem in s["memories"]:
            mem["session_id"] = sid
        sessions.append(s)

    sessions.sort(key=lambda s: s["start_time"], reverse=True)
    return sessions


def get_session_by_id(
    session_id: str,
    items: list[dict],
    gap_minutes: int = _GAP_MINUTES,
) -> dict[str, Any] | None:
    for s in detect_sessions(items, gap_minutes):
        if s["session_id"] == session_id:
            return s
    return None
