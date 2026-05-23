"""
Digital Soul Profile route.

GET /profile/summary   — behavioural profile from local memory metadata
"""

import logging

from fastapi import APIRouter

from app.services.memory_store import memory_store
from app.services.profile_service import get_profile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/summary")
async def profile_summary():
    """
    Return a privacy-first behavioural profile derived from local memory metadata.
    Includes: app usage, activity hours, scene distribution, and plain-English insights.
    """
    memories = memory_store.list()
    return get_profile(memories)
