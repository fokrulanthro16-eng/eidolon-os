"""
Replay Intelligence Service — Phase 13 AI Memory Replay Engine 2.0.

Provides enriched replay experiences beyond the basic session/replay endpoint:
  - Day replay    : all memories from a calendar date
  - Topic replay  : memories matching a text query, sorted chronologically
  - Modality replay: memories filtered by type (screenshot, pdf, voice, video)
  - Smart session : enhanced session replay with key moments + insights

Output schema (common to all replay types):
{
    replay_title:   str,
    summary:        str,
    ordered_events: list[dict],   # lightweight event dicts for timeline
    key_moments:    list[dict],   # notable moments with reasons
    apps_used:      list[str],
    memories:       list[dict],   # full memory items
    confidence:     float,
    total_count:    int,
    date_range:     {start, end} | None,
}
"""

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_MAX_REPLAY = 200   # cap memories returned per replay


# ---------------------------------------------------------------------------
# Date / time helpers
# ---------------------------------------------------------------------------

def _parse_dt(iso: str) -> datetime | None:
    try:
        s = iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _date_label(dt: datetime) -> str:
    today = _utc_now().date()
    d = dt.date()
    if d == today:
        return "Today"
    if d == today - timedelta(days=1):
        return "Yesterday"
    return dt.strftime("%A, %d %b %Y")


# ---------------------------------------------------------------------------
# Key-moment detection
# ---------------------------------------------------------------------------

_MOMENT_REASONS: list[tuple[str, str, str]] = [
    # (event_type_key, condition_description, priority)
    ("error_spike",   "Error / exception detected in OCR text", "high"),
    ("pdf_upload",    "PDF document ingested",                   "high"),
    ("voice_capture", "Voice memo recorded",                     "high"),
    ("camera_event",  "Live camera event detected",              "medium"),
    ("video_upload",  "Video uploaded and analysed",             "medium"),
    ("app_switch",    "Application switched",                    "low"),
    ("debug_start",   "Debugging session started",               "high"),
    ("ai_research",   "AI/LLM research detected",                "medium"),
]

import re

_DEBUG_PATS = [r"\bTraceback\b", r"\bException\b", r"\bError\b.*line \d+",
               r"\bTypeError\b", r"\bNameError\b", r"\bAttributeError\b"]
_AI_PATS    = [r"\bClaude\b", r"\bChatGPT\b", r"\bGPT-4\b", r"\banthropic\b",
               r"\bcopilot\b", r"\bgemini\b"]


def _is_debug(text: str) -> bool:
    return any(re.search(p, text, re.I | re.M) for p in _DEBUG_PATS)


def _is_ai_research(text: str) -> bool:
    return any(re.search(p, text, re.I | re.M) for p in _AI_PATS)


def _find_key_moments(memories: list[dict]) -> list[dict]:
    """Identify notable moments from an ordered list of memories."""
    moments: list[dict] = []
    seen_apps: set[str] = set()

    for m in memories:
        mtype  = m.get("type", "")
        text   = m.get("text") or ""
        meta   = m.get("metadata") or {}
        app    = meta.get("app_name") or meta.get("dominant_app", "")
        title  = m.get("title", "")
        ts     = m.get("created_at", "")

        # First occurrence of each app
        if app and app not in seen_apps:
            seen_apps.add(app)
            if len(moments) < 20:
                moments.append({
                    "memory_id":  m.get("id"),
                    "created_at": ts,
                    "title":      title,
                    "reason":     f"First time in {app} this session",
                    "priority":   "low",
                    "type":       "app_switch",
                })

        # Debugging detected
        if mtype == "screenshot" and _is_debug(text):
            moments.append({
                "memory_id":  m.get("id"),
                "created_at": ts,
                "title":      title,
                "reason":     "Error / exception in screen",
                "priority":   "high",
                "type":       "debug_start",
            })

        # AI research
        if mtype == "screenshot" and _is_ai_research(text):
            moments.append({
                "memory_id":  m.get("id"),
                "created_at": ts,
                "title":      title,
                "reason":     "AI research / chat session",
                "priority":   "medium",
                "type":       "ai_research",
            })

        # PDF upload
        if mtype == "pdf":
            moments.append({
                "memory_id":  m.get("id"),
                "created_at": ts,
                "title":      title,
                "reason":     "PDF document ingested",
                "priority":   "high",
                "type":       "pdf_upload",
            })

        # Voice
        if mtype == "voice":
            moments.append({
                "memory_id":  m.get("id"),
                "created_at": ts,
                "title":      title,
                "reason":     "Voice memo recorded",
                "priority":   "high",
                "type":       "voice_capture",
            })

        # Video / camera
        if mtype == "video":
            source = m.get("source", "")
            moments.append({
                "memory_id":  m.get("id"),
                "created_at": ts,
                "title":      title,
                "reason":     "Camera event detected" if source == "live_camera" else "Video analysed",
                "priority":   "medium",
                "type":       "camera_event" if source == "live_camera" else "video_upload",
            })

    # Deduplicate by memory_id, keep highest priority
    prio = {"high": 0, "medium": 1, "low": 2}
    by_id: dict[str, dict] = {}
    for m in moments:
        mid = m.get("memory_id")
        if mid and (mid not in by_id or prio[m["priority"]] < prio[by_id[mid]["priority"]]):
            by_id[mid] = m

    return sorted(by_id.values(), key=lambda x: x.get("created_at", ""))[:15]


# ---------------------------------------------------------------------------
# Light event converter
# ---------------------------------------------------------------------------

def _to_event(m: dict) -> dict:
    meta = m.get("metadata") or {}
    return {
        "id":           m.get("id"),
        "type":         m.get("type", ""),
        "title":        m.get("title", ""),
        "created_at":   m.get("created_at", ""),
        "app_name":     meta.get("app_name") or meta.get("dominant_app", ""),
        "scene_type":   meta.get("scene_type", ""),
        "workflow_type":meta.get("workflow_type", ""),
        "probable_task":meta.get("probable_task", ""),
        "source":       m.get("source", ""),
        "has_image":    bool(m.get("file_path")),
        "thumbnail_url":meta.get("thumbnail_url"),
    }


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def _build_summary(title: str, memories: list[dict]) -> str:
    if not memories:
        return "No memories found."
    types = Counter(m.get("type", "other") for m in memories)
    apps  = Counter(
        (m.get("metadata") or {}).get("app_name") or (m.get("metadata") or {}).get("dominant_app", "")
        for m in memories
        if (m.get("metadata") or {}).get("app_name") or (m.get("metadata") or {}).get("dominant_app")
    )
    parts = [f"{len(memories)} memories."]
    if types:
        type_str = ", ".join(f"{v} {k}" for k, v in types.most_common(4))
        parts.append(f"Types: {type_str}.")
    if apps:
        top_apps = [a for a, _ in apps.most_common(3)]
        parts.append(f"Apps: {', '.join(top_apps)}.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Shared result builder
# ---------------------------------------------------------------------------

def _build_result(title: str, memories: list[dict]) -> dict:
    if not memories:
        return {
            "replay_title":   title,
            "summary":        "No memories found for this replay.",
            "ordered_events": [],
            "key_moments":    [],
            "apps_used":      [],
            "memories":       [],
            "confidence":     0.0,
            "total_count":    0,
            "date_range":     None,
        }

    memories_sorted = sorted(memories, key=lambda m: m.get("created_at", ""))[:_MAX_REPLAY]
    apps = list(dict.fromkeys(
        a for m in memories_sorted
        for a in [(m.get("metadata") or {}).get("app_name") or (m.get("metadata") or {}).get("dominant_app", "")]
        if a
    ))
    dts = [_parse_dt(m.get("created_at", "")) for m in memories_sorted]
    dts = [d for d in dts if d]
    date_range = None
    if dts:
        date_range = {"start": min(dts).isoformat(), "end": max(dts).isoformat()}

    confidence = min(0.40 + 0.04 * len(memories_sorted), 0.92)

    return {
        "replay_title":   title,
        "summary":        _build_summary(title, memories_sorted),
        "ordered_events": [_to_event(m) for m in memories_sorted],
        "key_moments":    _find_key_moments(memories_sorted),
        "apps_used":      apps[:8],
        "memories":       memories_sorted,
        "confidence":     round(confidence, 2),
        "total_count":    len(memories_sorted),
        "date_range":     date_range,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def replay_day(date_str: str, memories: list[dict]) -> dict:
    """
    Return all memories from a specific calendar date (YYYY-MM-DD).
    Dates are matched against UTC created_at timestamps.
    """
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return _build_result(f"Day: {date_str}", [])

    filtered = []
    for m in memories:
        dt = _parse_dt(m.get("created_at", ""))
        if dt and dt.date() == target:
            filtered.append(m)

    label = _date_label(datetime.combine(target, datetime.min.time()).replace(tzinfo=timezone.utc))
    title = f"Replay: {label}"
    return _build_result(title, filtered)


def replay_topic(query: str, memories: list[dict], limit: int = 60) -> dict:
    """Return memories ranked by relevance to query, then sorted by time."""
    try:
        from app.services.search_service import search_memories
        results = search_memories(query, memories)
        matched = [r["item"] for r in results[:limit]]
    except Exception:
        # Fallback: simple keyword filter
        q = query.lower()
        matched = [
            m for m in memories
            if q in (m.get("text") or "").lower() or q in (m.get("title") or "").lower()
        ][:limit]

    title = f'Replay: "{query}"'
    return _build_result(title, matched)


def replay_modality(mem_type: str, memories: list[dict], limit: int = 100) -> dict:
    """Return memories of a specific type, ordered chronologically."""
    valid_types = {"screenshot", "pdf", "voice", "video", "image", "text"}
    if mem_type not in valid_types:
        return _build_result(f"Replay: {mem_type}", [])

    # 'video' matches both uploaded videos and live camera events
    if mem_type == "video":
        filtered = [m for m in memories if m.get("type") in ("video",)]
    else:
        filtered = [m for m in memories if m.get("type") == mem_type]

    type_labels = {
        "screenshot": "Screen Activity",
        "pdf":        "PDF Work",
        "voice":      "Voice Memos",
        "video":      "Video & Camera",
        "image":      "Images",
    }
    label = type_labels.get(mem_type, mem_type.capitalize())
    title = f"Replay: {label}"
    return _build_result(title, filtered[:limit])


def replay_session_smart(session_id: str, memories: list[dict]) -> dict:
    """Enhanced session replay with key moments and AI workflow insights."""
    try:
        from app.services.session_service import get_session_by_id
        session = get_session_by_id(session_id, memories)
    except Exception:
        session = None

    if not session:
        return _build_result(f"Session {session_id}", [])

    session_memories = session.get("memories", [])
    # Enrich with metadata from full memory store (session may only have light copies)
    mem_ids = {m.get("id") for m in session_memories}
    full_mems = [m for m in memories if m.get("id") in mem_ids]
    if not full_mems:
        full_mems = session_memories

    title = f"Replay: {session.get('title', session_id)}"
    result = _build_result(title, full_mems)

    # Inject session-level metadata
    result["session_id"]    = session_id
    result["session_title"] = session.get("title", "")
    result["duration_str"]  = session.get("duration_str", "")
    result["topics"]        = session.get("topics", [])
    result["keywords"]      = session.get("keywords", [])
    return result
