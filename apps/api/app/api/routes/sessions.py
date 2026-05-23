"""
Session router.

Endpoints
---------
GET /sessions/list                  All detected work sessions (slim, no memories)
GET /sessions/{session_id}          Single session with full memory items
GET /sessions/{session_id}/replay   Chronological frames for playback
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.services.memory_store import memory_store
from app.services.session_service import detect_sessions, get_session_by_id
from app.services.session_store import session_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/list")
async def list_sessions(
    gap_minutes:   int  = Query(default=15, ge=1, le=1440),
    force_refresh: bool = Query(default=False, description="Bypass the session cache and recompute"),
):
    """
    Return all detected work sessions, newest first.

    Sessions are computed from memory timestamps and persisted to
    storage/session-db/sessions.json.  Subsequent calls return the cache
    until the memory count or gap_minutes changes.

    Pass force_refresh=true to recompute unconditionally.
    """
    items = memory_store.list()
    slim  = session_store.get_or_refresh(items, gap_minutes=gap_minutes, force=force_refresh)

    logger.info(
        "sessions/list: %d sessions from %d memories (cached=%s)",
        len(slim), len(items), not force_refresh,
    )
    return {
        "count":       len(slim),
        "gap_minutes": gap_minutes,
        "sessions":    slim,
    }


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    gap_minutes: int = Query(default=15, ge=1, le=1440),
):
    """
    Return a single session with its full memory items.
    Memory items include a 'session_id' field for cross-referencing.
    Always performs a fresh lookup (detail views need complete data).
    """
    items   = memory_store.list()
    session = get_session_by_id(session_id, items, gap_minutes=gap_minutes)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Session '{session_id}' not found. "
                "It may have merged with an adjacent session if gap_minutes changed."
            ),
        )

    logger.info(
        "sessions/%s: %d memories  duration=%s",
        session_id, session["memory_count"], session["duration_str"],
    )
    return session


@router.get("/{session_id}/replay")
async def replay_session(
    session_id:  str,
    gap_minutes: int = Query(default=15, ge=1, le=1440),
):
    """
    Return session memories sorted chronologically for frame-by-frame playback.

    Each frame includes: timestamp, time_offset_secs, app_name, window_title,
    ocr_summary (first 200 chars), file_path, and type.
    """
    items   = memory_store.list()
    session = get_session_by_id(session_id, items, gap_minutes=gap_minutes)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )

    # Sort memories chronologically (oldest first = frame 0)
    memories = sorted(
        session["memories"],
        key=lambda m: m.get("created_at", ""),
    )

    # Parse session start for time-offset computation
    try:
        start_dt = datetime.fromisoformat(session["start_time"])
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
    except Exception:
        start_dt = None

    frames = []
    for i, mem in enumerate(memories):
        meta        = mem.get("metadata") or {}
        ocr_text    = mem.get("text") or ""
        ocr_summary = ocr_text[:200] + ("…" if len(ocr_text) > 200 else "")

        time_offset = 0
        if start_dt:
            try:
                t = datetime.fromisoformat(mem.get("created_at", ""))
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                time_offset = max(0, int((t - start_dt).total_seconds()))
            except Exception:
                pass

        frames.append({
            "index":            i,
            "memory_id":        mem.get("id", ""),
            "timestamp":        mem.get("created_at", ""),
            "time_offset_secs": time_offset,
            "title":            mem.get("title", ""),
            "app_name":         meta.get("app_name"),
            "window_title":     meta.get("window_title"),
            "exe_name":         meta.get("exe_name"),
            "ocr_text":         ocr_text,
            "ocr_summary":      ocr_summary,
            "file_path":        mem.get("file_path"),
            "type":             mem.get("type", "screenshot"),
            "source":           mem.get("source", ""),
            "tags":             mem.get("tags") or [],
        })

    logger.info("sessions/%s/replay: %d frames", session_id, len(frames))

    return {
        "session_id":    session["session_id"],
        "title":         session["title"],
        "start_time":    session["start_time"],
        "end_time":      session["end_time"],
        "duration_secs": session["duration_secs"],
        "duration_str":  session["duration_str"],
        "frame_count":   len(frames),
        "frames":        frames,
    }
