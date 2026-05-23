"""
Agent endpoints — Phase 12 EIDOLON OS Agent Mode.

POST /agent/execute        — execute a named agent action
GET  /agent/actions        — list available actions
GET  /agent/status         — screen-watch status + current workflow
GET  /agent/daily-summary  — today's activity summary
GET  /agent/workflow       — workflow timeline (last 24h)
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.agent_service import execute_action, get_screen_watch_status, list_actions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


class ExecuteRequest(BaseModel):
    action: str
    args: dict = {}


@router.post("/execute", summary="Execute an agent action")
async def agent_execute(req: ExecuteRequest):
    """
    Execute a named EIDOLON agent action.

    All actions are local-only, safe, and non-destructive.
    Returns a result dict with at minimum: success (bool) and message (str).
    """
    result = execute_action(req.action, req.args)
    return result


@router.get("/actions", summary="List available agent actions")
async def agent_actions():
    """Return the registry of safe agent actions with descriptions and arg schemas."""
    return {"actions": list_actions()}


@router.get("/status", summary="Agent and screen-watch status")
async def agent_status():
    """Return screen-watch running state and current workflow context."""
    try:
        from app.services.memory_store import memory_store
        from app.services.workflow_service import get_current_workflow
        memories = memory_store.list()
        current_wf = get_current_workflow(memories)
    except Exception:
        current_wf = {"active": False, "label": "Unknown"}

    return {
        "screen_watch_running": get_screen_watch_status(),
        "current_workflow":     current_wf,
    }


@router.get("/daily-summary", summary="Daily activity summary from memory")
async def agent_daily_summary(hours: float = 24.0):
    """
    Generate a summary of the user's activity over the last `hours` hours.
    Powered entirely by local memory analysis — no LLM required.
    """
    try:
        from app.services.memory_store import memory_store
        from app.services.workflow_service import get_daily_summary
        memories = memory_store.list()
        return get_daily_summary(memories, hours=hours)
    except Exception as exc:
        return {"error": str(exc), "summary_text": "Could not generate summary."}


@router.get("/workflow", summary="Workflow timeline (last 24h)")
async def agent_workflow(hours: float = 24.0):
    """
    Return a list of workflow periods detected from screen captures.
    Each period includes label, duration, dominant app, and detected tools.
    """
    try:
        from app.services.memory_store import memory_store
        from app.services.workflow_service import get_workflow_timeline
        memories = memory_store.list()
        timeline = get_workflow_timeline(memories, hours=hours)
        return {"periods": timeline, "count": len(timeline)}
    except Exception as exc:
        return {"periods": [], "count": 0, "error": str(exc)}
