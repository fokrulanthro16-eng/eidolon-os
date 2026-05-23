"""
Autonomous Suggestions routes.

GET  /suggestions           — grounded suggestions (up to 5)
GET  /suggestions/list      — alias for GET /suggestions
POST /suggestions/{id}/dismiss  — dismiss a suggestion persistently
"""

import logging

from fastapi import APIRouter, HTTPException

from app.services.memory_store import memory_store
from app.services.suggestion_service import dismiss_suggestion, get_suggestions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/suggestions", tags=["suggestions"])


def _response(memories):
    suggestions = get_suggestions(memories)
    return {"count": len(suggestions), "suggestions": suggestions}


@router.get("", summary="List grounded suggestions from memory patterns")
async def list_suggestions():
    """Return up to 5 grounded suggestions backed by actual memory items."""
    return _response(memory_store.list())


@router.get("/list", summary="List grounded suggestions (alias)")
async def list_suggestions_alias():
    """Alias for GET /suggestions."""
    return _response(memory_store.list())


@router.post("/{suggestion_id}/dismiss", summary="Dismiss a suggestion persistently")
async def dismiss(suggestion_id: str):
    """
    Mark a suggestion as dismissed. It will not appear in future responses
    until the suggestion cache regenerates with new content.
    """
    ok = dismiss_suggestion(suggestion_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to persist dismissal")
    return {"dismissed": True, "suggestion_id": suggestion_id}
