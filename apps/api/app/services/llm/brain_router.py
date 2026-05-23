"""
Brain Router — Phase 18.

Selects and caches the active brain based on the BRAIN_PROVIDER env var.

BRAIN_PROVIDER=local_semantic  (default — always works, zero dependencies)
BRAIN_PROVIDER=ollama          (probe Ollama; falls back to local_semantic)
BRAIN_PROVIDER=lmstudio        (probe LM Studio; falls back to local_semantic)

The existing app.services.llm.get_brain() (used by /chat routes) is unchanged.
This router is used only by the new /brain/* endpoints (Phase 18).
"""

import logging
import os
from typing import Any

from app.services.llm.base import BaseBrain

logger = logging.getLogger(__name__)

_active_brain: BaseBrain | None = None


def get_active_brain() -> BaseBrain:
    """Return the Phase-18 brain singleton, selected by BRAIN_PROVIDER."""
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

    if provider == "ollama":
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

    # Default: local_semantic (always works)
    from app.services.llm.local_brain import LocalBrain
    return LocalBrain()


def get_brain_status() -> dict[str, Any]:
    """Return status dict for the active brain."""
    brain = get_active_brain()
    provider = os.environ.get("BRAIN_PROVIDER", "local_semantic").lower().strip()
    base: dict[str, Any] = {
        "brain_provider":    provider,
        "mode":              brain.mode().value,
        "llm_active":        brain.is_llm_active(),
        "fallback_used":     provider != "local_semantic" and not brain.is_llm_active(),
    }
    if hasattr(brain, "status"):
        base.update(brain.status())
    return base
