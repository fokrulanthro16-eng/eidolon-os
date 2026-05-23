"""
LLM brain package.

Usage
-----
    from app.services.llm import get_brain

    brain = get_brain()
    answer = brain.generate_response(user_message, memories, context)

The singleton is created once on first call and reused for the lifetime
of the process. Changing OLLAMA_URL / OLLAMA_MODEL env vars requires a
process restart to take effect.
"""

from app.services.llm.base import BaseBrain, BrainMode
from app.services.llm.local_brain import LocalBrain

_brain: LocalBrain | None = None


def get_brain() -> LocalBrain:
    """Return the process-wide brain singleton, creating it if necessary."""
    global _brain
    if _brain is None:
        _brain = LocalBrain()
    return _brain


__all__ = ["get_brain", "BaseBrain", "BrainMode", "LocalBrain"]
