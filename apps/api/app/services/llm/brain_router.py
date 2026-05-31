"""
Brain Router — Phase 18 / 21.

Selects and caches the active brain based on the BRAIN_PROVIDER env var.

BRAIN_PROVIDER=local_semantic  (default — always works, zero dependencies)
BRAIN_PROVIDER=ollama          (probe Ollama; falls back to local_semantic)
BRAIN_PROVIDER=lmstudio        (probe LM Studio; falls back to local_semantic)
BRAIN_PROVIDER=gemini          (Phase 21: Google Gemini via free AI Studio key)

The existing app.services.llm.get_brain() (used by /chat routes) is unchanged.
This router is used only by the /brain/* endpoints.
"""

import logging
import os
from typing import Any

from app.services.llm.base import BaseBrain, BrainMode

logger = logging.getLogger(__name__)

_active_brain: BaseBrain | None = None


def get_active_brain() -> BaseBrain:
    """Return the active brain singleton, selected by BRAIN_PROVIDER."""
    global _active_brain
    if _active_brain is None:
        _active_brain = _build()
    return _active_brain


def reset_active_brain() -> None:
    """Force re-probe on next get_active_brain() call."""
    global _active_brain
    _active_brain = None
    logger.info("brain_router: reset — will re-probe on next call")


def _build() -> BaseBrain:
    provider = os.environ.get("BRAIN_PROVIDER", "local_semantic").lower().strip()
    logger.info("brain_router: BRAIN_PROVIDER=%s", provider)

    if provider == "gemini":
        try:
            brain = _build_gemini_brain()
            if brain is not None and brain.is_llm_active():
                logger.info("brain_router: Gemini active")
                return brain
            logger.warning("brain_router: Gemini unavailable → local_semantic")
        except Exception as exc:
            logger.warning("brain_router: GeminiBrain failed (%s) → local_semantic", exc)

    elif provider == "ollama":
        try:
            from app.services.llm.ollama_brain import OllamaBrain
            brain = OllamaBrain()
            if brain.is_llm_active():
                logger.info("brain_router: Ollama active")
                return brain
            logger.warning("brain_router: Ollama unavailable → local_semantic")
        except Exception as exc:
            logger.warning("brain_router: OllamaBrain failed (%s) → local_semantic", exc)

    elif provider == "lmstudio":
        try:
            from app.services.llm.lmstudio_brain import LMStudioBrain
            brain = LMStudioBrain()
            if brain.is_llm_active():
                logger.info("brain_router: LM Studio active")
                return brain
            logger.warning("brain_router: LM Studio unavailable → local_semantic")
        except Exception as exc:
            logger.warning("brain_router: LMStudioBrain failed (%s) → local_semantic", exc)

    # Default: local_semantic (always works, zero deps)
    from app.services.llm.local_brain import LocalBrain
    return LocalBrain()


def _build_gemini_brain() -> BaseBrain | None:
    """Wrap GeminiBridgeService in a BaseBrain adapter (shared singleton)."""
    from app.services.gemini_bridge_service import get_gemini_service

    svc = get_gemini_service()

    class _GeminiBrain(BaseBrain):
        """Thin BaseBrain adapter around GeminiBridgeService."""

        def mode(self) -> BrainMode:
            return BrainMode.REMOTE_LLM if svc.is_active() else BrainMode.LOCAL_SEMANTIC

        def is_llm_active(self) -> bool:
            return svc.is_active()

        def generate_response(self, user_message, memories, context=None):
            return svc.generate_response(user_message, memories, context)

        def generate_with_history(self, user_message, context, history=None):
            return svc.generate_with_history(user_message, context, history)

        def generate_stream(self, user_message, context, history=None):
            yield from svc.generate_stream(user_message, context, history)

        def status(self) -> dict[str, Any]:
            return svc.status()

    return _GeminiBrain()


def get_brain_status() -> dict[str, Any]:
    """Return status dict for the active brain, including orb_state for the frontend."""
    brain    = get_active_brain()
    provider = os.environ.get("BRAIN_PROVIDER", "local_semantic").lower().strip()
    llm_ok   = brain.is_llm_active()
    fallback = provider != "local_semantic" and not llm_ok

    # orb_state: green = LLM live, yellow = local/fallback, red = reserved for client
    orb_state = "green" if llm_ok else "yellow"

    base: dict[str, Any] = {
        "brain_provider": provider,
        "mode":           brain.mode().value,
        "llm_active":     llm_ok,
        "fallback_used":  fallback,
        "orb_state":      orb_state,
    }
    if hasattr(brain, "status"):
        base.update(brain.status())
        # Restore top-level fields that status() may have overwritten
        base["brain_provider"] = provider
        base["orb_state"]      = orb_state
    return base
