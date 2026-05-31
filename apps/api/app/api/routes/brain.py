"""
Brain Status + Chat endpoints — Phase 18 / 21.

GET  /brain/status   — current brain provider, availability, and orb_state
POST /brain/chat     — chat grounded in memories, using active brain
POST /brain/reset    — force re-probe (e.g. after starting Ollama/LM Studio)

Default provider: local_semantic (zero dependencies, always works).
Optional providers: ollama | lmstudio | gemini (set BRAIN_PROVIDER in .env).

/brain/chat routing logic
-------------------------
When BRAIN_PROVIDER=gemini:
    GeminiBridgeService is called directly — the brain_router singleton's
    is_llm_active() gate is intentionally bypassed so a temporary init
    failure or deprecated-SDK auth delay cannot silently downgrade the
    response to local_semantic without the caller knowing.
    Response fields: provider=gemini, brain_mode=gemini_hybrid.

All other providers (local_semantic / ollama / lmstudio):
    Existing brain_router.get_active_brain() path — unchanged.

orb_state in /brain/status:
  green  — LLM provider is live (Ollama / LM Studio / Gemini)
  yellow — no LLM; running local_semantic (always functional)
  red    — computed on the frontend when the backend is unreachable
"""

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import BRAIN_PROVIDER

if TYPE_CHECKING:
    from app.services.gemini_bridge_service import GeminiBridgeService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/brain", tags=["brain"])

def _get_gemini_svc() -> "GeminiBridgeService":
    """Return the shared GeminiBridgeService singleton (same instance as /chat/*)."""
    from app.services.gemini_bridge_service import get_gemini_service
    return get_gemini_service()


class BrainChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: Optional[list[dict]] = None


@router.get("/status", summary="Current brain provider and availability")
async def brain_status():
    """
    Returns the active brain mode, provider, availability, and orb_state.

    brain_provider: local_semantic | ollama | lmstudio | gemini
    mode:           local_semantic | local_llm | remote_llm | gemini_hybrid
    llm_active:     true if an LLM (local or cloud) is reachable
    fallback_used:  true if provider ≠ local_semantic but LLM unavailable
    orb_state:      green (LLM live) | yellow (local fallback) — red set by client
    """
    from app.services.llm.brain_router import get_brain_status

    status = get_brain_status()

    # When provider is gemini, overwrite status with live GeminiBridgeService state
    if BRAIN_PROVIDER == "gemini":
        svc         = _get_gemini_svc()
        active      = svc.is_active()
        last_detail = svc._last_call_detail   # {} on success, dict on any error

        # Quota exceeded means calls will fail until the window resets.
        # Treat service as effectively unavailable so orb/mode/fallback_used
        # reflect actual usability — not just init state.
        quota_limited    = (
            isinstance(last_detail, dict)
            and last_detail.get("status") == "quota_exceeded"
        )
        effective_active = active and not quota_limited

        status["brain_provider"]    = "gemini"
        status["mode"]              = "gemini_hybrid" if effective_active else "local_semantic"
        status["llm_active"]        = effective_active
        status["fallback_used"]     = not effective_active
        status["orb_state"]         = "green" if effective_active else "yellow"
        status["provider"]          = "gemini"
        status["model"]             = svc._model_name
        status["tools_loaded"]      = len(svc._tools)
        status["error"]             = svc._error if not active else ""
        status["last_call_error"]   = svc._last_call_error
        status["last_call_detail"]  = last_detail
        status["quota_limited"]     = quota_limited
        if quota_limited:
            status["retry_after_seconds"] = last_detail.get("retry_after_seconds", 0)

    return status


@router.post("/chat", summary="Chat with active brain, grounded in local memories")
async def brain_chat(req: BrainChatRequest):
    """
    Answers a question using the active brain, with memory context injected.

    When BRAIN_PROVIDER=gemini:
        Calls GeminiBridgeService directly.  The brain_router singleton's
        is_llm_active() guard is bypassed so a transient init failure cannot
        silently swap the provider to local_semantic.
        Response: provider=gemini, brain_mode=gemini_hybrid, fallback_used=false.

    All other providers:
        Uses brain_router.get_active_brain() — unchanged behaviour.
    """
    from app.services.llm.memory_context import build_memory_context
    from app.services.memory_store import memory_store
    from app.services.search_service import search_memories

    memories = memory_store.list()
    matches  = search_memories(req.message.strip(), memories)[:8]
    context  = build_memory_context(
        user_message  = req.message,
        query_used    = req.message,
        raw_matches   = matches,
        time_filtered = False,
        all_items     = memories,
    )

    # ── Gemini branch — explicit, bypasses brain_router fallback gate ──
    if BRAIN_PROVIDER == "gemini":
        svc    = _get_gemini_svc()
        answer = svc.generate_with_history(req.message, context, req.history or [])

        call_err      = svc._last_call_error        # "" on success
        call_detail   = svc._last_call_detail       # structured error dict, {} on success
        gemini_active = svc.is_active()
        failed        = bool(call_err) or not gemini_active

        base = {
            "answer":           answer,
            "provider":         "gemini",
            "brain_mode":       "gemini_hybrid" if gemini_active and not call_err else "local_semantic",
            "llm_active":       gemini_active,
            "fallback_used":    failed,
            "sources_count":    len(matches),
            "error":            call_err,
        }

        # When the call failed, include the structured quota / error fields so
        # the frontend and callers get the exact information they need without
        # having to parse the raw error string.
        if call_detail:
            base["status"]               = call_detail.get("status", "error")
            base["retry_after_seconds"]  = call_detail.get("retry_after_seconds", 0)
            base["http_code"]            = call_detail.get("http_code", 0)
            base["grpc_status"]          = call_detail.get("grpc_status", "")

        return base

    # ── Local / Ollama / LM Studio branch — unchanged ─────────────────
    from app.services.llm.brain_router import get_active_brain
    brain  = get_active_brain()
    answer = brain.generate_with_history(req.message, context, req.history or [])
    return {
        "answer":        answer,
        "brain_mode":    brain.mode().value,
        "llm_active":    brain.is_llm_active(),
        "fallback_used": not brain.is_llm_active(),
        "sources_count": len(matches),
    }


@router.post("/reset", summary="Re-probe the brain provider")
async def brain_reset():
    """
    Force re-probe: clears the brain_router singleton and the shared
    GeminiBridgeService singleton so the next request rebuilds from scratch.
    """
    import app.services.gemini_bridge_service as _gbs
    _gbs._svc_singleton = None                           # clear shared Gemini singleton

    from app.services.llm.brain_router import get_active_brain, reset_active_brain
    reset_active_brain()
    brain = get_active_brain()

    extra: dict = {}
    if BRAIN_PROVIDER == "gemini":
        svc                      = _get_gemini_svc()
        extra["provider"]        = "gemini"
        extra["gemini_active"]   = svc.is_active()
        extra["tools_loaded"]    = len(svc._tools)
        extra["gemini_error"]    = svc._error if not svc.is_active() else ""

    return {
        "message":    "Brain re-probed.",
        "mode":       brain.mode().value,
        "llm_active": brain.is_llm_active(),
        **extra,
    }
