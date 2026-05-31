"""
GeminiBridgeService — Phase 21 (updated: google-genai new SDK).

Uses google-genai (from google import genai) — the current supported SDK.
google.generativeai (0.8.x) is deprecated and no longer receives updates.

Activated when BRAIN_PROVIDER=gemini and GEMINI_API_KEY is set.
Key format is NOT validated at init time — auth errors surface on the first
API call with a clear error field rather than silently falling back.

Agentic loop: Gemini can call local tools (search_memories, get_daily_summary,
get_user_profile, list_sessions) up to 4 rounds before returning a final answer.

Error surfacing:
  _last_call_error  — set on every generate call; "" when call succeeded.
  status()          — exposes init error and last call error.
  brain.py reads _last_call_error to populate fallback_used + error fields.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Generator

logger = logging.getLogger(__name__)

_MAX_TOOL_ROUNDS = 4


# ---------------------------------------------------------------------------
# Gemini error classifier
# ---------------------------------------------------------------------------

def _parse_retry_seconds(exc: Exception) -> int:
    """Extract the retryDelay value (in seconds) from a quota error."""
    # 1. Try structured details: {"error": {"details": [{"@type": "..RetryInfo", "retryDelay": "26s"}]}}
    details_obj = getattr(exc, "details", None)
    if isinstance(details_obj, dict):
        error_obj = details_obj.get("error", details_obj)
        for d in error_obj.get("details", []):
            if "RetryInfo" in d.get("@type", ""):
                m = re.search(r"(\d+)", d.get("retryDelay", "0s"))
                if m:
                    return int(m.group(1))
    # 2. Regex fallback on the string representation
    m = re.search(r"retryDelay[^0-9]*(\d+)", str(exc), re.IGNORECASE)
    return int(m.group(1)) if m else 0


def _classify_gemini_error(exc: Exception) -> dict[str, Any]:
    """
    Inspect a google-genai exception and return a structured error dict.

    Fields:
      type               — machine tag: quota_exceeded | auth_error |
                           model_not_found | api_error
      status             — same tag (matches the requested JSON field name)
      retry_after_seconds — seconds to wait before retrying (0 if unknown)
      message            — original Gemini error message
      http_code          — HTTP status integer (0 if unavailable)
      grpc_status        — gRPC status string (e.g. RESOURCE_EXHAUSTED)
      provider           — always "gemini"
    """
    http_code   = getattr(exc, "code",    0) or 0
    grpc_status = getattr(exc, "status",  "") or ""
    message     = getattr(exc, "message", "") or str(exc)

    msg_lower = message.lower() + grpc_status.lower()

    if (
        http_code == 429
        or "resource_exhausted" in msg_lower
        or "quota" in msg_lower
        or "generaterequests" in message   # GenerateRequestsPerDay…
    ):
        return {
            "type":                 "quota_exceeded",
            "status":               "quota_exceeded",
            "retry_after_seconds":  _parse_retry_seconds(exc),
            "message":              message,
            "http_code":            http_code,
            "grpc_status":          grpc_status,
            "provider":             "gemini",
        }

    if http_code in (401, 403) or "unauthenticated" in msg_lower or "permission_denied" in msg_lower:
        return {
            "type":                "auth_error",
            "status":              "auth_error",
            "retry_after_seconds": 0,
            "message":             message,
            "http_code":           http_code,
            "grpc_status":         grpc_status,
            "provider":            "gemini",
        }

    if http_code == 404 or "not_found" in msg_lower or "not found" in msg_lower:
        return {
            "type":                "model_not_found",
            "status":              "model_not_found",
            "retry_after_seconds": 0,
            "message":             message,
            "http_code":           http_code,
            "grpc_status":         grpc_status,
            "provider":            "gemini",
        }

    return {
        "type":                "api_error",
        "status":              "api_error",
        "retry_after_seconds": 0,
        "message":             message or str(exc),
        "http_code":           http_code,
        "grpc_status":         grpc_status,
        "provider":            "gemini",
    }


_svc_singleton: "GeminiBridgeService | None" = None


def get_gemini_service() -> "GeminiBridgeService":
    """
    Process-wide GeminiBridgeService singleton.
    Shared by brain.py (/brain/*) and chat.py (/chat/*) so that
    _last_call_error / _last_call_detail are always consistent.
    """
    global _svc_singleton
    if _svc_singleton is None:
        _svc_singleton = GeminiBridgeService()
    return _svc_singleton


class GeminiBridgeService:
    """
    Wraps google-genai to satisfy the BaseBrain protocol.
    Standalone (does not subclass BaseBrain) so that importing this file
    never raises even when the SDK is absent.
    """

    def __init__(self) -> None:
        from app.core.config import GEMINI_API_KEY, GEMINI_ALLOW_SYSTEM_LOCKDOWN, GEMINI_MODEL

        self._api_key         = GEMINI_API_KEY.strip()
        self._model_name      = GEMINI_MODEL.strip() or "gemini-2.0-flash"
        self._lockdown        = GEMINI_ALLOW_SYSTEM_LOCKDOWN
        self._active               = False
        self._client               = None
        self._tools: list          = []
        self._error: str           = ""
        self._last_call_error: str = ""
        self._last_call_detail: dict[str, Any] = {}

        if not self._api_key or self._api_key == "your_free_ai_studio_key_here":
            self._error = "GEMINI_API_KEY not set in apps/api/.env"
            logger.warning("GeminiBridgeService: %s", self._error)
            return

        try:
            from google import genai                          # new SDK
            from app.services.gemini_tool_registry import EIDOLON_TOOLS

            self._client = genai.Client(api_key=self._api_key)
            self._tools  = EIDOLON_TOOLS or []
            self._active = True

            logger.info(
                "GeminiBridgeService: model=%s  tools=%d  lockdown=%s",
                self._model_name,
                len(self._tools),
                self._lockdown,
            )

        except ImportError as exc:
            self._error = f"google-genai not installed — run: pip install google-genai ({exc})"
            logger.warning("GeminiBridgeService: %s", self._error)
        except Exception as exc:
            self._error = str(exc)
            logger.warning("GeminiBridgeService: init failed — %s", exc)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def is_active(self) -> bool:
        return self._active

    def generate_with_history(
        self,
        user_message: str,
        context: dict[str, Any],
        history: list[dict] | None = None,
    ) -> str:
        self._last_call_error  = ""
        self._last_call_detail = {}

        if not self._active or self._client is None:
            self._last_call_error  = self._error or "Gemini not initialised"
            self._last_call_detail = {
                "type": "not_initialised", "status": "not_initialised",
                "message": self._last_call_error, "retry_after_seconds": 0,
                "provider": "gemini",
            }
            return self._local_fallback(user_message, context)

        try:
            from google.genai import types as genai_types
            from app.services.gemini_tool_registry import execute_tool

            prompt = self._build_prompt(user_message, context, history or [])

            # Only pass tools when there are tools to pass — an empty list
            # causes SDK validation errors in some versions of google-genai.
            config_kwargs: dict[str, Any] = {
                "temperature":      0.35,
                "max_output_tokens": 512,
            }
            if self._tools:
                config_kwargs["tools"] = self._tools
            config = genai_types.GenerateContentConfig(**config_kwargs)

            # Create a fresh chat session for this request
            chat = self._client.chats.create(model=self._model_name, config=config)
            response = chat.send_message(prompt)

            # ── Agentic tool-call loop ───────────────────────────────
            for _round in range(_MAX_TOOL_ROUNDS):
                fn_calls = getattr(response, "function_calls", None) or []
                if not fn_calls:
                    break

                tool_parts = []
                for fc in fn_calls:
                    result = execute_tool(fc.name, dict(fc.args))
                    logger.info(
                        "GeminiBridgeService: tool=%s  result_type=%s",
                        fc.name,
                        type(result).__name__,
                    )
                    tool_parts.append(
                        genai_types.Part.from_function_response(
                            name=fc.name,
                            response={"result": str(result)[:2000]},
                        )
                    )

                response = chat.send_message(tool_parts)
            # ────────────────────────────────────────────────────────

            answer = (response.text or "").strip()
            if not answer:
                raise ValueError("Gemini returned empty response after tool loop")

            logger.debug("GeminiBridgeService: ok  chars=%d", len(answer))
            return answer

        except Exception as exc:
            detail                 = _classify_gemini_error(exc)
            self._last_call_detail = detail
            self._last_call_error  = detail["message"] or str(exc)
            logger.warning(
                "GeminiBridgeService: call failed  type=%s  http=%s  retry=%ss  msg=%s",
                detail["type"], detail["http_code"],
                detail["retry_after_seconds"], detail["message"],
            )
            return self._local_fallback(user_message, context)

    def generate_from_prompt(self, prompt: str, max_tokens: int = 400) -> str:
        """
        Simple prompt → text, no memory context, no tools, no history.
        Used by the intelligence service for profile and timeline synthesis.
        Returns empty string on failure (caller supplies fallback).
        """
        if not self._active or self._client is None:
            return ""
        try:
            from google.genai import types as genai_types
            config = genai_types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=max_tokens,
            )
            chat     = self._client.chats.create(model=self._model_name, config=config)
            response = chat.send_message(prompt)
            return (response.text or "").strip()
        except Exception as exc:
            logger.warning("GeminiBridgeService: generate_from_prompt failed — %s", exc)
            return ""

    def generate_response(
        self,
        user_message: str,
        memories: list,
        context: dict[str, Any] | None = None,
    ) -> str:
        return self.generate_with_history(user_message, context or {}, [])

    def generate_stream(
        self,
        user_message: str,
        context: dict[str, Any],
        history: list[dict] | None = None,
    ) -> Generator[str, None, None]:
        """
        Streaming synthesis — uses models.generate_content() (no tools, no chat
        session) so memory context is fed directly in the prompt.

        This is the most reliable Gemini code path: no tool declarations,
        no chat-session state, no empty-list SDK validation errors.
        The answer is yielded word-by-word to drive the frontend streaming UI.
        """
        self._last_call_error  = ""
        self._last_call_detail = {}

        if not self._active or self._client is None:
            self._last_call_error  = self._error or "Gemini not initialised"
            self._last_call_detail = {
                "type": "not_initialised", "status": "not_initialised",
                "message": self._last_call_error, "retry_after_seconds": 0,
                "provider": "gemini",
            }
            yield self._local_fallback(user_message, context)
            return

        try:
            from google.genai import types as genai_types

            prompt = self._build_prompt(user_message, context, history or [])

            # chats.create() WITHOUT tools — same SDK entry point as
            # generate_with_history (which is confirmed working).
            # models.generate_content() is a different code path in the SDK
            # and has been observed to fail where chats.create() succeeds.
            # Memory context is already embedded in the prompt so no tool
            # calls are needed for this synthesis.
            config = genai_types.GenerateContentConfig(
                temperature=0.35,
                max_output_tokens=600,
            )
            chat   = self._client.chats.create(model=self._model_name, config=config)
            response = chat.send_message(prompt)

            answer = (response.text or "").strip()
            if not answer:
                raise ValueError("Gemini returned empty response")

            logger.debug("GeminiBridgeService: stream synthesis ok  chars=%d", len(answer))

            # Yield word-by-word so the SSE stream sends incremental deltas
            words = answer.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                if chunk:
                    yield chunk

        except Exception as exc:
            detail                 = _classify_gemini_error(exc)
            self._last_call_detail = detail
            self._last_call_error  = detail["message"] or str(exc)
            logger.warning(
                "GeminiBridgeService: stream synthesis failed  type=%s  http=%s  msg=%s",
                detail["type"], detail["http_code"], detail["message"],
            )
            yield self._local_fallback(user_message, context)

    # ------------------------------------------------------------------
    # Status dict
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        return {
            "provider":          "gemini",
            "model":             self._model_name,
            "llm_active":        self._active,
            "fallback_used":     not self._active,
            "lockdown":          self._lockdown,
            "tools_loaded":      len(self._tools),
            "error":             self._error if not self._active else "",
            "last_call_error":   self._last_call_error,
            "last_call_detail":  self._last_call_detail,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    # Signals that the user wants pattern inference, not a keyword lookup.
    # Detected at prompt-build time to switch to the reasoning system prompt.
    _REASONING_SIGNALS: frozenset = frozenset({
        "who am i", "who are you", "what am i", "who i am",
        "what patterns", "what do you see", "what do you know about me",
        "what can you tell", "what can you infer",
        "summarize", "summary", "recent activity",
        "based on my memories", "based on the memories",
        "tell me about me", "tell me about my", "describe me",
        "my activity", "my work", "my habits", "my profile", "my history",
        "what have i been",
        "what am i building", "active projects", "what should i work on",
        "work on next", "what should i focus", "what are my projects",
    })

    _SYSTEM_DEFAULT = (
        "You are EIDOLON OS — a local-first AI cognitive assistant.\n"
        "You help users recall and understand their digital activity.\n\n"
        "INSTRUCTIONS:\n"
        "- Read the memory context below and synthesise a natural, conversational answer.\n"
        "- Write 2–4 complete sentences as a paragraph — never a bullet list.\n"
        "- Describe what the memories show in plain language (e.g. 'You were working on...').\n"
        "- If no memories are provided, answer from general knowledge as EIDOLON OS.\n"
        "- Never repeat raw memory text verbatim. Paraphrase and connect ideas."
    )

    _SYSTEM_REASONING = (
        "You are EIDOLON OS — a local-first AI cognitive assistant.\n"
        "The user wants you to infer patterns, identity, or insights from their captured memories.\n\n"
        "INSTRUCTIONS:\n"
        "- Use the IDENTITY CONTEXT and MEMORY CONTEXT below to answer the question directly.\n"
        "- Write 3–5 complete sentences as a connected narrative paragraph.\n"
        "- For 'Who am I?' or 'What am I building?': name the specific project and domain clearly.\n"
        "- For 'What are my active projects?': list the named projects with a brief description of each.\n"
        "- For 'What should I work on next?': give ONE specific, actionable recommendation.\n"
        "- Use phrasing like: 'You appear to be...', 'Based on your activity...', 'You are building...'.\n"
        "- Make confident, specific inferences — never say 'I cannot determine' or 'I found N memories'.\n"
        "- Never count or enumerate raw memories. Synthesise everything into a natural narrative."
    )

    def _build_prompt(
        self,
        user_message: str,
        context: dict[str, Any],
        history: list[dict],
    ) -> str:
        parts: list[str] = []

        # Choose system prompt: reasoning mode for identity/pattern questions,
        # default synthesis mode for everything else.
        msg_lower = user_message.lower()
        is_reasoning = any(s in msg_lower for s in self._REASONING_SIGNALS)
        system = self._SYSTEM_REASONING if is_reasoning else self._SYSTEM_DEFAULT

        if not self._lockdown:
            summary: str = context.get("activity_summary", "")
            # compressed is the enriched list; fall back to raw_matches
            compressed: list = context.get("compressed") or context.get("raw_matches", [])

            # Build snippet block from whichever source has data
            snippets: list[str] = []
            for m in compressed[:8]:
                item  = m.get("item", m)   # flat for compressed, nested for raw_matches
                title = (item.get("title", "") or m.get("title", "")).strip()
                text  = (item.get("text",  "") or m.get("text",  "") or "").strip()[:300]
                rel   = m.get("relative", "")
                tag   = f" [{rel}]" if rel else ""
                if title or text:
                    snippets.append(f"• {title}{tag}: {text}" if title else f"• {text}")

            if snippets:
                mem_block = "MEMORY CONTEXT:\n" + "\n".join(snippets)
                header = f"{system}\n\n{mem_block}"
                if summary:
                    header += f"\n\nRECENT ACTIVITY:\n{summary}"
                parts.append(header)
            elif summary:
                parts.append(f"{system}\n\nRECENT ACTIVITY:\n{summary}")
            else:
                parts.append(system)

        # Identity context — available on reasoning/identity queries
        identity = context.get("identity")
        if identity and is_reasoning:
            proj_list = [
                p["name"] for p in identity.get("active_projects", [])[:4]
                if p.get("status") in ("active", "recent")
            ]
            # EIDOLON OS is the parent project — always lead so Gemini names it first
            proj_list.sort(key=lambda n: (0 if "EIDOLON" in n else 1))
            primary  = proj_list[0] if proj_list else ""
            projects = ", ".join(proj_list)
            focus    = identity.get("current_focus", "")
            goals    = "; ".join(identity.get("inferred_goals", [])[:3])
            if projects or focus:
                id_lines = ["IDENTITY CONTEXT:"]
                if primary:  id_lines.append(f"Primary project: {primary}")
                if projects: id_lines.append(f"Active projects: {projects}")
                if focus and focus != primary:
                    id_lines.append(f"Current focus (sub-task/module): {focus}")
                elif focus:
                    id_lines.append(f"Current focus: {focus}")
                if goals:    id_lines.append(f"Inferred goals:  {goals}")
                parts.append("\n".join(id_lines))

        if history:
            conv: list[str] = []
            for turn in history[-6:]:
                role    = turn.get("role", "user")
                content = turn.get("content", "")
                conv.append(f"{role.upper()}: {content}")
            if conv:
                parts.append("CONVERSATION HISTORY:\n" + "\n".join(conv))

        parts.append(f"USER: {user_message}\nASSISTANT:")
        return "\n\n".join(parts)

    # Signals that _local_fallback should produce a reasoning paragraph,
    # not enumerate memory titles.
    _REASONING_FALLBACK_SIGNALS: frozenset = frozenset({
        "who am i", "who are you", "what am i", "who i am",
        "what patterns", "what do you see", "what do you know about me",
        "what can you tell", "what can you infer",
        "summarize", "summary", "recent activity",
        "based on my memories", "based on the memories",
        "tell me about me", "tell me about my", "describe me",
        "my activity", "my work", "my habits", "my profile", "my history",
        "what have i been", "what kind of work",
        "what am i building", "active projects", "what should i work on",
        "work on next", "what should i focus", "what are my projects",
    })

    @staticmethod
    def _local_fallback(user_message: str, context: dict[str, Any]) -> str:
        """
        Fallback when the Gemini API call fails.

        For reasoning / identity questions → synthesise a pattern-inference
        paragraph from memory titles and sources (never enumerate items).
        For specific-lookup questions → brief factual summary.
        For empty database → honest "no memories yet" message.
        """
        items_source: list = (
            context.get("compressed") or context.get("raw_matches") or []
        )
        activity_summary: str = context.get("activity_summary", "")

        # ── Empty database ────────────────────────────────────────────────
        if not items_source and not activity_summary:
            return (
                "Your memory database is empty. Start the screen watcher to begin "
                "capturing activity, then ask me again."
            )

        # Detect reasoning / pattern question
        msg_lower = user_message.lower()
        is_reasoning = any(
            s in msg_lower
            for s in GeminiBridgeService._REASONING_FALLBACK_SIGNALS
        )

        if is_reasoning:
            # Prefer pre-built identity context when available
            identity = context.get("identity", {})
            if identity:
                user_summary = identity.get("user_summary", "")
                if user_summary and len(user_summary) > 40:
                    return user_summary
                msg_l      = user_message.lower()
                proj_active = [
                    p["name"] for p in identity.get("active_projects", [])
                    if p.get("status") in ("active", "recent")
                ]
                # EIDOLON OS is the parent — lead with it
                proj_active.sort(key=lambda n: (0 if "EIDOLON" in n else 1))
                if "next" in msg_l or "work on" in msg_l or "focus" in msg_l:
                    suggestion = identity.get("suggested_next", "")
                    if suggestion:
                        return suggestion
                    if proj_active:
                        return f"Continue working on {proj_active[0]}. It is your most active project right now."
                if "projects" in msg_l:
                    if proj_active:
                        focus = identity.get("current_focus", "")
                        return (
                            f"Your active projects are: {', '.join(proj_active)}. "
                            f"Current focus: {focus or proj_active[0]}."
                        )
                # General identity question — delegate to the canonical synthesiser
                try:
                    from app.services.identity_service import local_identity_summary
                    result = local_identity_summary(identity)
                    if result:
                        return result
                except Exception:
                    pass

        if is_reasoning and items_source:
            # Infer domain patterns from titles and sources without enumerating
            all_text = " ".join(
                (m.get("item", m).get("title", "") or m.get("title", ""))
                for m in items_source
            ).lower()
            sources = {
                (m.get("item", m).get("source") or m.get("source") or "").strip()
                for m in items_source
                if (m.get("item", m).get("source") or m.get("source"))
            }

            domains: list[str] = []
            if any(w in all_text for w in ("camera", "detection", "person", "object", "vision", "cctv", "stationary")):
                domains.append("camera monitoring and computer vision")
            if any(w in all_text for w in ("code", "python", "function", "class", "import", "vscode", "cursor")):
                domains.append("software development")
            if any(w in all_text for w in ("browser", "chrome", "web", "http", "search", "firefox")):
                domains.append("web browsing and research")
            if any(w in all_text for w in ("document", "pdf", "word", "excel", "sheet", "notion")):
                domains.append("document and knowledge work")
            if any(w in all_text for w in ("terminal", "shell", "command", "git", "deploy")):
                domains.append("system administration and DevOps")

            count  = len(items_source)
            src_str = ", ".join(sorted(sources)) if sources else "your local environment"

            if domains:
                primary   = domains[0]
                secondary = f" alongside {domains[1]}" if len(domains) > 1 else ""
                return (
                    f"Based on your recent memories, you appear to be actively working on "
                    f"{primary}{secondary}. "
                    f"EIDOLON OS has captured {count} recent events from {src_str}, "
                    f"and the recurring themes in those events point to a focus on {primary}. "
                    f"This suggests ongoing work — possibly testing, development, or monitoring — "
                    f"in that space."
                )
            else:
                return (
                    f"Based on {count} recent memories from {src_str}, you have been actively "
                    f"using your system. The activity spans multiple recorded events but no single "
                    f"dominant pattern is immediately apparent from the available data. "
                    f"Try asking about a specific app or task to get more targeted insights."
                )

        # ── Specific-lookup fallback (non-reasoning) ──────────────────────
        if items_source:
            count = len(items_source)
            # Pick the most informative title to surface
            top_title = ""
            for m in items_source[:3]:
                item = m.get("item", m)
                t = (item.get("title") or m.get("title") or "").strip()
                if t:
                    top_title = t
                    break
            rel = (items_source[0].get("relative") or "recently") if items_source else "recently"

            if count == 1 and top_title:
                return f"The most relevant memory I found was: {top_title} ({rel})."
            elif count > 1 and top_title:
                return (
                    f"I found {count} relevant memories. The most recent was: "
                    f"{top_title} ({rel}). Ask a more specific question to narrow the results."
                )
            return f"I found {count} relevant memories. Ask a more specific question for details."

        # ── Activity summary only ─────────────────────────────────────────
        if activity_summary and activity_summary != "No recent activity captured.":
            return (
                f"Your recent activity: {activity_summary}. "
                "Ask about a specific app, task, or time range for more detail."
            )

        return (
            "Your memory database is empty. Start the screen watcher to begin "
            "capturing activity, then ask me again."
        )
