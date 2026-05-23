"""
World Model Intelligence endpoints — Phase 17.

GET /world/state         — current world state snapshot
GET /world/predictions   — active movement predictions
GET /world/events        — recent camera + video events
"""

import logging

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/world", tags=["world-model"])


@router.get("/state", summary="World state snapshot")
async def world_state():
    """
    Aggregated snapshot of the current scene:
      - active entities (persons, vehicles, objects seen recently)
      - movement predictions (estimated, heuristic)
      - zone map (left/center/right × top/mid/bottom)
      - risk notes (all labeled [Estimated])
      - activity timeline
      - confidence score

    Disclaimer: heuristic only — not a security system.
    """
    from app.services.memory_store import memory_store
    from app.services.prediction_service import camera_tracker
    from app.services.world_model_service import get_world_state

    memories    = memory_store.list()
    predictions = camera_tracker.get_active()
    return get_world_state(memories, predictions)


@router.get("/predictions", summary="Active movement predictions")
async def world_predictions():
    """Return active object predictions from the live camera tracker."""
    from app.services.prediction_service import camera_tracker
    preds = camera_tracker.get_active()
    return {
        "predictions": preds,
        "count":       len(preds),
        "note":        "[Estimated] Heuristic linear velocity extrapolation. 1.5s horizon.",
    }


@router.get("/events", summary="Recent camera and video events timeline")
async def world_events(limit: int = Query(default=20, ge=1, le=100)):
    """Return the most recent camera/video detection events."""
    from app.services.memory_store import memory_store
    from app.services.world_model_service import get_recent_camera_events
    memories = memory_store.list()
    events   = get_recent_camera_events(memories, limit=limit)
    return {"events": events, "count": len(events)}
