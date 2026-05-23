"""
LocalBrain — default brain for EIDOLON OS.

Default mode: LOCAL_SEMANTIC
    Semantic search (sentence-transformers) + rule-based synthesis.
    Zero external dependencies. Works offline. No API key required.

Optional upgrade: LOCAL_LLM (Ollama)
    Set OLLAMA_ENABLED=true in apps/api/.env to activate.
    Requires Ollama to be installed and running locally.
    Falls back to LOCAL_SEMANTIC automatically if Ollama is unreachable.

Future: REMOTE_LLM (cloud)
    Not implemented. Placeholder for optional cloud upgrade path.
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Generator

from app.core.config import OLLAMA_BASE_URL, OLLAMA_ENABLED, OLLAMA_MODEL
from app.services.llm.base import BaseBrain, BrainMode, MemoryEntry

logger = logging.getLogger(__name__)

_HEALTH_TIMEOUT   = 2
_GENERATE_TIMEOUT = 90


class LocalBrain(BaseBrain):

    def __init__(self) -> None:
        self._ollama_url      = OLLAMA_BASE_URL.rstrip("/")
        self._model           = OLLAMA_MODEL
        self._ollama_enabled  = OLLAMA_ENABLED
        self._llm_active      = False
        self._available_models: list[str] = []

        if self._ollama_enabled:
            self._llm_active, self._available_models = self._probe_ollama()
            if self._llm_active:
                models_str = ", ".join(self._available_models) or "(none pulled)"
                logger.info(
                    "LocalBrain: Ollama ONLINE  model=%s  available=%s",
                    self._model, models_str,
                )
                if self._model not in (m.split(":")[0] for m in self._available_models):
                    logger.warning(
                        "Model '%s' not in Ollama. Run: ollama pull %s",
                        self._model, self._model,
                    )
            else:
                logger.warning(
                    "LocalBrain: Ollama enabled but not reachable at %s — "
                    "falling back to Local Semantic mode. "
                    "Run 'ollama serve' then restart the API.",
                    self._ollama_url,
                )
        else:
            logger.info(
                "LocalBrain: Local Semantic mode active "
                "(Ollama disabled — set OLLAMA_ENABLED=true in .env to upgrade)",
            )

    # ------------------------------------------------------------------
    # BaseBrain required
    # ------------------------------------------------------------------

    def mode(self) -> BrainMode:
        if self._llm_active:
            return BrainMode.LOCAL_LLM
        return BrainMode.LOCAL_SEMANTIC

    def is_llm_active(self) -> bool:
        return self._llm_active

    def generate_response(
        self,
        user_message: str,
        memories: list[MemoryEntry],
        context: dict[str, Any] | None = None,
    ) -> str:
        if self._llm_active and context is not None:
            try:
                return self._call_ollama_chat(user_message, context, history=[])
            except Exception as exc:
                logger.warning("Ollama call failed (%s) — falling back to semantic mode", exc)
                self._llm_active, _ = self._probe_ollama()
        return self._semantic_synthesis(context)

    # ------------------------------------------------------------------
    # BaseBrain optional overrides
    # ------------------------------------------------------------------

    def generate_with_history(
        self,
        user_message: str,
        context: dict[str, Any],
        history: list[dict] | None = None,
    ) -> str:
        if self._llm_active:
            try:
                return self._call_ollama_chat(user_message, context, history or [])
            except Exception as exc:
                logger.warning("Ollama chat failed (%s) — falling back", exc)
                self._llm_active, _ = self._probe_ollama()
        return self._semantic_synthesis(context)

    def generate_stream(
        self,
        user_message: str,
        context: dict[str, Any],
        history: list[dict] | None = None,
    ) -> Generator[str, None, None]:
        if self._llm_active:
            try:
                yield from self._stream_ollama_chat(user_message, context, history or [])
                return
            except Exception as exc:
                logger.warning("Ollama stream failed (%s) — falling back", exc)
                self._llm_active, _ = self._probe_ollama()
        yield self._semantic_synthesis(context)

    # ------------------------------------------------------------------
    # Semantic synthesis (always available, zero deps)
    # ------------------------------------------------------------------

    def _semantic_synthesis(self, context: dict | None) -> str:
        """
        Synthesise a natural-language answer from the memory context dict.
        Uses the rule-based engine which operates on already-ranked,
        semantically-filtered matches — so the answer is grounded in
        semantic search results even without an LLM.
        """
        from app.services.chat_memory_service import synthesize_answer
        if context is None:
            return "Memory recall unavailable — no context provided."
        return synthesize_answer(
            query_used=context.get("query_used", ""),
            matches=context.get("raw_matches", []),
            time_filtered=context.get("time_filtered", False),
        )

    # ------------------------------------------------------------------
    # Ollama /api/chat — non-streaming (only used when OLLAMA_ENABLED=true)
    # ------------------------------------------------------------------

    def _call_ollama_chat(
        self,
        user_message: str,
        context: dict,
        history: list[dict],
    ) -> str:
        from app.services.llm.prompt_builder import build_chat_messages_with_history
        messages = build_chat_messages_with_history(user_message, context, history)
        payload = json.dumps({
            "model":    self._model,
            "messages": messages,
            "stream":   False,
            "options":  {"temperature": 0.3, "num_predict": 350},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self._ollama_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_GENERATE_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        answer = data.get("message", {}).get("content", "").strip()
        if not answer:
            raise ValueError("Ollama returned empty response")
        logger.info("Ollama: model=%s eval_count=%s", self._model, data.get("eval_count", "?"))
        return answer

    # ------------------------------------------------------------------
    # Ollama /api/chat — streaming
    # ------------------------------------------------------------------

    def _stream_ollama_chat(
        self,
        user_message: str,
        context: dict,
        history: list[dict],
    ) -> Generator[str, None, None]:
        from app.services.llm.prompt_builder import build_chat_messages_with_history
        messages = build_chat_messages_with_history(user_message, context, history)
        payload = json.dumps({
            "model":    self._model,
            "messages": messages,
            "stream":   True,
            "options":  {"temperature": 0.3, "num_predict": 350},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self._ollama_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_GENERATE_TIMEOUT) as resp:
            for raw_line in resp:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("message", {}).get("content", "")
                if delta:
                    yield delta
                if chunk.get("done"):
                    break

    # ------------------------------------------------------------------
    # Health probe
    # ------------------------------------------------------------------

    def _probe_ollama(self) -> tuple[bool, list[str]]:
        try:
            req = urllib.request.urlopen(
                f"{self._ollama_url}/api/tags", timeout=_HEALTH_TIMEOUT
            )
            if req.status != 200:
                return False, []
            data = json.loads(req.read().decode("utf-8"))
            return True, [m["name"] for m in data.get("models", [])]
        except Exception:
            return False, []

    # ------------------------------------------------------------------
    # Status (exposed via GET /system/info and GET /system/ollama)
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        return {
            "mode":             self.mode().value,
            "llm_active":       self._llm_active,
            "ollama_enabled":   self._ollama_enabled,
            "ollama_url":       self._ollama_url,
            "ollama_model":     self._model,
            "available_models": self._available_models,
        }
