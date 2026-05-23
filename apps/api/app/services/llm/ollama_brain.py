"""
Ollama Brain — Phase 18.

Subclass of LocalBrain that always probes Ollama on construction
(regardless of the OLLAMA_ENABLED env var used by the legacy path).

Used when BRAIN_PROVIDER=ollama.
Falls back to LOCAL_SEMANTIC automatically if Ollama is unreachable.
No model download. No crash. No required dependency.
"""

import os
from typing import Any

from app.services.llm.local_brain import LocalBrain


class OllamaBrain(LocalBrain):
    """LocalBrain with mandatory Ollama probe regardless of OLLAMA_ENABLED."""

    def __init__(self) -> None:
        self._ollama_url     = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        self._model          = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
        self._ollama_enabled = True   # force probe
        self._available_models: list[str] = []
        self._llm_active, self._available_models = self._probe_ollama()

    def status(self) -> dict[str, Any]:
        s = super().status()
        s["provider"]      = "ollama"
        s["fallback_used"] = not self._llm_active
        return s
