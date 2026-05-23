"""
Digital Soul Intelligence endpoints — Phase 14.

GET /soul/profile         — full behavioral profile
GET /soul/patterns        — named behavioral patterns with evidence
GET /soul/workflow-rhythm — hourly activity heatmap
GET /soul/project-memory  — recurring projects and unfinished work
"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/soul", tags=["digital-soul"])


@router.get("/profile", summary="Full Digital Soul behavioral profile")
async def soul_profile():
    """
    Comprehensive behavioral profile synthesising all memory metadata.
    Extends /profile/summary with workflow patterns and project continuity.
    Privacy-first: analyses only timestamps, app names, and keyword frequencies.
    """
    from app.services.digital_soul_service import get_soul_profile
    from app.services.memory_store import memory_store
    return get_soul_profile(memory_store.list())


@router.get("/patterns", summary="Named behavioral patterns")
async def soul_patterns():
    """
    Return detected behavioral patterns (Coding Focus, Active Researcher, etc.)
    Each pattern includes a description, evidence, and strength score (0–1).
    Language is grounded in actual memory evidence — no inference beyond the data.
    """
    from app.services.digital_soul_service import get_patterns
    from app.services.memory_store import memory_store
    return get_patterns(memory_store.list())


@router.get("/workflow-rhythm", summary="Hourly workflow activity heatmap")
async def soul_workflow_rhythm():
    """
    Return an hour-by-hour and day-of-week breakdown of memory activity.
    Useful for understanding personal peak productivity hours.
    """
    from app.services.digital_soul_service import get_workflow_rhythm
    from app.services.memory_store import memory_store
    return get_workflow_rhythm(memory_store.list())


@router.get("/project-memory", summary="Recurring projects and unfinished work")
async def soul_project_memory():
    """
    Identify recurring project names from window titles, frequent topics,
    and sessions that appear to have been interrupted or left unfinished.
    """
    from app.services.digital_soul_service import get_project_memory
    from app.services.memory_store import memory_store
    return get_project_memory(memory_store.list())
