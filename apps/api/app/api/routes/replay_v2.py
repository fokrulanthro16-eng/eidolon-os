"""
Replay Engine 2.0 endpoints — Phase 13.

GET /replay/day?date=YYYY-MM-DD         — all memories from a calendar date
GET /replay/topic?query=...             — topic-filtered chronological replay
GET /replay/modality?type=screenshot    — single-modality replay
GET /replay/session/{session_id}/smart  — enhanced session replay with insights
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/replay", tags=["replay"])


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@router.get("/day", summary="Replay memories from a specific date")
async def replay_day(date: str = Query(default=None, description="YYYY-MM-DD (defaults to today)")):
    """
    Return all memories from a calendar date in chronological order,
    with key-moment detection and a short summary.
    """
    from app.services.memory_store import memory_store
    from app.services.replay_intelligence_service import replay_day as _replay_day
    target = date or _today_str()
    memories = memory_store.list()
    return _replay_day(target, memories)


@router.get("/topic", summary="Replay memories by topic / keyword query")
async def replay_topic(
    query: str = Query(..., description="Search query for topic-based replay"),
    limit: int = Query(default=60, ge=1, le=200),
):
    """
    Return memories ranked by relevance to a query, then sorted chronologically.
    Useful for: "show me my YOLO work", "when was I debugging FastAPI", etc.
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    from app.services.memory_store import memory_store
    from app.services.replay_intelligence_service import replay_topic as _replay_topic
    memories = memory_store.list()
    return _replay_topic(query.strip(), memories, limit=limit)


@router.get("/modality", summary="Replay memories by modality / type")
async def replay_modality(
    type: str = Query(..., description="Memory type: screenshot|pdf|voice|video|image"),
    limit: int = Query(default=100, ge=1, le=200),
):
    """
    Return memories of a specific modality in chronological order.
    Supports: screenshot, pdf, voice, video, image.
    """
    allowed = {"screenshot", "pdf", "voice", "video", "image", "text"}
    if type not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid type '{type}'. Allowed: {', '.join(sorted(allowed))}",
        )
    from app.services.memory_store import memory_store
    from app.services.replay_intelligence_service import replay_modality as _replay_modality
    memories = memory_store.list()
    return _replay_modality(type, memories, limit=limit)


@router.get("/session/{session_id}/smart", summary="Enhanced smart session replay")
async def replay_session_smart(session_id: str):
    """
    Return an enriched session replay with:
      - Key moments (debugging, uploads, AI research, app switches)
      - Workflow summary
      - Apps used and topics covered
    """
    from app.services.memory_store import memory_store
    from app.services.replay_intelligence_service import replay_session_smart as _replay_smart
    memories = memory_store.list()
    result = _replay_smart(session_id, memories)
    if result.get("total_count", 0) == 0 and not result.get("session_id"):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return result
