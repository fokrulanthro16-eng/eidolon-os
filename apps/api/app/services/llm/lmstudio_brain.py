"""
LM Studio Brain — Phase 18.

LM Studio exposes an OpenAI-compatible REST API at http://127.0.0.1:1234/v1
This brain uses only the standard library (urllib) — no openai package needed.

Used when BRAIN_PROVIDER=lmstudio.
Falls back to local_semantic if LM Studio is unreachable or returns errors.
No crash. No required dependency. No model download.
"""

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Generator

from app.services.llm.base import BaseBrain, BrainMode, MemoryEntry

logger = logging.getLogger(__name__)

_HEALTH_TIMEOUT   = 2
_GENERATE_TIMEOUT = 90


class LMStudioBrain(BaseBrain):

    def __init__(self) -> None:
        self._base_url         = os.environ.get(
            "LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1"
        ).rstrip("/")
        self._model            = os.environ.get("LMSTUDIO_MODEL", "local-model")
        self._llm_active       = False
        self._available_models: list[str] = []
        self._llm_active, self._available_models = self._probe()

    # ------------------------------------------------------------------
    # BaseBrain required
    # ------------------------------------------------------------------

    def mode(self) -> BrainMode:
        return BrainMode.LOCAL_LLM if self._llm_active else BrainMode.LOCAL_SEMANTIC

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
                return self._call(user_message, context, [])
            except Exception as exc:
                logger.warning("LM Studio call failed (%s) — fallback", exc)
                self._llm_active = False
        return self._semantic_fallback(context)

    def generate_with_history(
        self,
        user_message: str,
        context: dict[str, Any],
        history: list[dict] | None = None,
    ) -> str:
        if self._llm_active:
            try:
                return self._call(user_message, context, history or [])
            except Exception as exc:
                logger.warning("LM Studio chat failed (%s) — fallback", exc)
                self._llm_active = False
        return self._semantic_fallback(context)

    def generate_stream(
        self,
        user_message: str,
        context: dict[str, Any],
        history: list[dict] | None = None,
    ) -> Generator[str, None, None]:
        if self._llm_active:
            try:
                yield from self._stream(user_message, context, history or [])
                return
            except Exception as exc:
                logger.warning("LM Studio stream failed (%s) — fallback", exc)
                self._llm_active = False
        yield self._semantic_fallback(context)

    def status(self) -> dict[str, Any]:
        return {
            "mode":             self.mode().value,
            "provider":         "lmstudio",
            "llm_active":       self._llm_active,
            "lmstudio_url":     self._base_url,
            "lmstudio_model":   self._model,
            "available_models": self._available_models,
            "fallback_used":    not self._llm_active,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _semantic_fallback(self, context: dict | None) -> str:
        from app.services.chat_memory_service import synthesize_answer
        if context is None:
            return "Memory recall unavailable — no context provided."
        return synthesize_answer(
            query_used   = context.get("query_used", ""),
            matches      = context.get("raw_matches", []),
            time_filtered= context.get("time_filtered", False),
        )

    def _build_messages(
        self,
        user_message: str,
        context: dict[str, Any],
        history: list[dict],
    ) -> list[dict]:
        from app.services.llm.prompt_builder import SYSTEM_PROMPT, build_user_prompt
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in history[-6:]:
            messages.append({
                "role":    h.get("role", "user"),
                "content": h.get("content", ""),
            })
        messages.append({"role": "user", "content": build_user_prompt(user_message, context)})
        return messages

    def _call(
        self,
        user_message: str,
        context: dict[str, Any],
        history: list[dict],
    ) -> str:
        payload = json.dumps({
            "model":       self._model,
            "messages":    self._build_messages(user_message, context, history),
            "stream":      False,
            "temperature": 0.3,
            "max_tokens":  350,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_GENERATE_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        answer = data["choices"][0]["message"]["content"].strip()
        if not answer:
            raise ValueError("LM Studio returned empty content")
        logger.info("LMStudio: model=%s tokens=%s", self._model, data.get("usage", {}).get("completion_tokens", "?"))
        return answer

    def _stream(
        self,
        user_message: str,
        context: dict[str, Any],
        history: list[dict],
    ) -> Generator[str, None, None]:
        payload = json.dumps({
            "model":       self._model,
            "messages":    self._build_messages(user_message, context, history),
            "stream":      True,
            "temperature": 0.3,
            "max_tokens":  350,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_GENERATE_TIMEOUT) as resp:
            for raw_line in resp:
                line = raw_line.strip()
                if not line or line == b"data: [DONE]":
                    continue
                if line.startswith(b"data: "):
                    try:
                        chunk = json.loads(line[6:].decode("utf-8"))
                        delta = chunk["choices"][0].get("delta", {}).get("content", "")
                        if delta:
                            yield delta
                    except Exception:
                        continue

    def _probe(self) -> tuple[bool, list[str]]:
        try:
            req = urllib.request.urlopen(
                f"{self._base_url}/models", timeout=_HEALTH_TIMEOUT
            )
            if req.status != 200:
                return False, []
            data   = json.loads(req.read().decode("utf-8"))
            models = [m["id"] for m in data.get("data", [])]
            return True, models
        except Exception:
            return False, []
