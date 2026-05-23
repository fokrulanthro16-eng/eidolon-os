"""
Memory context builder.

Transforms raw search results into a structured context dict that
both the rule-based fallback and the LLM prompt builder consume.
Centralising this prevents the two paths from diverging over time.
"""

import re
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_utc(iso: str) -> datetime | None:
    try:
        t = datetime.fromisoformat(iso)
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _relative_time(t: datetime) -> str:
    diff = datetime.now(timezone.utc) - t
    secs = diff.total_seconds()
    if secs < 60:
        return "just now"
    if secs < 3600:
        m = int(secs / 60)
        return f"{m} min{'s' if m != 1 else ''} ago"
    if secs < 86400:
        h = int(secs / 3600)
        return f"{h} hr{'s' if h != 1 else ''} ago"
    if diff.days == 1:
        return f"yesterday at {t.astimezone().strftime('%H:%M')}"
    if diff.days < 7:
        return f"{diff.days} days ago"
    return t.astimezone().strftime("%b %d, %H:%M")


_NOISE = frozenset(
    "file edit view help window terminal code format tools settings "
    "explorer source control extensions ocr unavailable image stored "
    "successfully engine configured yet run start stop build debug "
    "test open close new save copy paste undo redo find replace".split()
)


def _extract_text_keywords(text: str, n: int = 10) -> list[str]:
    """Return up to n distinctive words from OCR text, skipping noise."""
    if "[OCR" in text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for w in re.findall(r"\b[A-Za-z][a-zA-Z]{3,}\b", text):
        wl = w.lower()
        if wl not in _NOISE and wl not in seen:
            seen.add(wl)
            out.append(w)
            if len(out) >= n:
                break
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compress_memories(
    matches: list[dict],
    max_items: int = 6,
    max_text_chars: int = 300,
) -> list[dict]:
    """
    Trim a list of scored matches to fit within a token budget.

    Returns a list of dicts ready for the prompt builder:
        score       int
        title       str
        type        str
        source      str
        created_at  str  (ISO)
        relative    str  (human-readable age)
        text        str  (truncated OCR)
        keywords    list[str]
    """
    compressed = []
    for m in matches[:max_items]:
        item = m["item"]
        ts = _parse_utc(item.get("created_at", ""))
        text = item.get("text", "")
        if "[OCR" in text:
            text = ""
        compressed.append({
            "score":      m["score"],
            "title":      item.get("title", ""),
            "type":       item.get("type", ""),
            "source":     item.get("source", ""),
            "created_at": item.get("created_at", ""),
            "relative":   _relative_time(ts) if ts else "",
            "text":       text[:max_text_chars],
            "keywords":   _extract_text_keywords(item.get("text", "")),
        })
    return compressed


def recent_activity_summary(items: list[dict], n: int = 5) -> str:
    """
    One-line summary of the most recent n memory items.
    Useful as a quick 'what has the user been doing lately' hint for the LLM.

    Example output:
        "Recent activity: Screen Capture (screen_capture), GitHub dashboard
         (Chrome), EIDOLON Test Window (VSCode) — 3 sessions"
    """
    recent = sorted(
        items,
        key=lambda x: x.get("created_at", ""),
        reverse=True,
    )[:n]

    if not recent:
        return "No recent activity captured."

    parts = [f"{i.get('title', '?')} ({i.get('source', '?')})" for i in recent]
    return "Recent: " + ", ".join(parts) + f" — {len(items)} total memories"


def build_memory_context(
    user_message: str,
    query_used: str,
    raw_matches: list[dict],
    time_filtered: bool,
    time_start: Any = None,
    time_end: Any = None,
    all_items: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Build the unified context dict consumed by both the rule-based fallback
    and the LLM prompt builder.

    Keys
    ----
    user_message        str
    query_used          str
    time_filtered       bool
    time_window         str    human-readable time window description
    total_count         int    total matches (before top-N slice)
    raw_matches         list   full scored match list (for rule-based path)
    compressed          list   trimmed, enriched entries (for LLM prompt)
    activity_summary    str    recent activity one-liner
    sources             list[str]
    newest_relative     str
    oldest_relative     str
    """
    compressed = compress_memories(raw_matches)

    # Time window description
    time_window = "all time"
    if time_filtered and time_start:
        start_str = time_start.astimezone().strftime("%b %d %H:%M")
        end_str   = time_end.astimezone().strftime("%b %d %H:%M") if time_end else "now"
        time_window = f"{start_str} to {end_str}"

    # Source list
    sources = sorted({m["item"].get("source", "") for m in raw_matches if m["item"].get("source")})

    # Newest / oldest relative timestamps
    timestamps = [
        _parse_utc(m["item"].get("created_at", ""))
        for m in raw_matches
        if m["item"].get("created_at")
    ]
    timestamps = [t for t in timestamps if t]
    newest_relative = _relative_time(max(timestamps)) if timestamps else ""
    oldest_relative = _relative_time(min(timestamps)) if timestamps else ""

    # Activity summary from all stored items (optional)
    activity_summary = ""
    if all_items is not None:
        activity_summary = recent_activity_summary(all_items)

    return {
        "user_message":     user_message,
        "query_used":       query_used,
        "time_filtered":    time_filtered,
        "time_window":      time_window,
        "total_count":      len(raw_matches),
        "raw_matches":      raw_matches,
        "compressed":       compressed,
        "activity_summary": activity_summary,
        "sources":          sources,
        "newest_relative":  newest_relative,
        "oldest_relative":  oldest_relative,
    }
