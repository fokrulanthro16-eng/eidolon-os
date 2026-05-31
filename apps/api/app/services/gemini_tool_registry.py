"""
GeminiToolRegistry — Phase 21.

Declarative registry of Gemini function-calling tool definitions.

These definitions are passed to the Gemini model so it can request
local operations (memory search, daily summary, profile, sessions).
Actual execution is dispatched by execute_tool() called from the
GeminiBridgeService agentic loop.

Tool builder targets google-genai (new SDK).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Raw tool definitions — JSON-Schema style, SDK-agnostic
# ---------------------------------------------------------------------------

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "search_memories",
        "description": (
            "Search the user's local memory store for relevant past events, "
            "notes, screenshots, documents, or conversations. "
            "Returns the top matching memory items."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language query describing what to look for.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 6).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_daily_summary",
        "description": (
            "Retrieve a structured summary of the user's activity for today "
            "or the last N hours, including apps used, tasks worked on, and "
            "session count."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "hours": {
                    "type": "integer",
                    "description": "How many hours back to summarise (default 24).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_user_profile",
        "description": (
            "Retrieve the user's behavioural profile: top apps, "
            "main topics, typical work patterns, most-used file types."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "list_sessions",
        "description": (
            "List recent work sessions captured by EIDOLON OS, "
            "with start/end times, duration, and main topics."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of sessions to return (default 10).",
                },
            },
            "required": [],
        },
    },
]

# ---------------------------------------------------------------------------
# Executor map — correct implementations, lazily imported
# ---------------------------------------------------------------------------

def _exec_search_memories(args: dict[str, Any]) -> Any:
    from app.services.memory_store import memory_store
    from app.services.search_service import search_memories
    query   = args.get("query", "")
    limit   = int(args.get("limit", 6))
    results = search_memories(query, memory_store.list())[:limit]
    return [
        {
            "id":         r.get("item", {}).get("id", ""),
            "title":      r.get("item", {}).get("title", ""),
            "text":       (r.get("item", {}).get("text", "") or "")[:400],
            "score":      r.get("score", 0),
            "created_at": r.get("item", {}).get("created_at", ""),
        }
        for r in results
    ]


def _exec_get_daily_summary(args: dict[str, Any]) -> Any:
    # get_daily_summary lives in workflow_service, not agent_service
    from app.services.workflow_service import get_daily_summary
    from app.services.memory_store import memory_store
    hours = int(args.get("hours", 24))
    try:
        return get_daily_summary(memory_store.list(), hours=hours)
    except Exception as exc:
        logger.warning("tool get_daily_summary failed: %s", exc)
        return {"error": "daily summary unavailable"}


def _exec_get_user_profile(_args: dict[str, Any]) -> Any:
    # get_profile requires memories argument
    from app.services.profile_service import get_profile
    from app.services.memory_store import memory_store
    try:
        return get_profile(memory_store.list())
    except Exception as exc:
        logger.warning("tool get_user_profile failed: %s", exc)
        return {"error": "profile unavailable"}


def _exec_list_sessions(args: dict[str, Any]) -> Any:
    # get_sessions is a method on session_store singleton, not a module function
    from app.services.session_store import session_store
    limit = int(args.get("limit", 10))
    try:
        return session_store.get_sessions()[:limit]
    except Exception as exc:
        logger.warning("tool list_sessions failed: %s", exc)
        return []


_EXECUTOR_MAP: dict[str, Any] = {
    "search_memories":   _exec_search_memories,
    "get_daily_summary": _exec_get_daily_summary,
    "get_user_profile":  _exec_get_user_profile,
    "list_sessions":     _exec_list_sessions,
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_tool_definitions() -> list[dict[str, Any]]:
    """Return raw tool definitions (SDK-agnostic)."""
    return _TOOL_DEFS


def execute_tool(name: str, args: dict[str, Any]) -> Any:
    """Dispatch a tool call by name. Always returns; never raises."""
    fn = _EXECUTOR_MAP.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        result = fn(args)
        logger.info("tool executed: %s → %s items", name, len(result) if isinstance(result, (list, dict)) else 1)
        return result
    except Exception as exc:
        logger.warning("tool %s raised: %s", name, exc)
        return {"error": str(exc)}


def _json_type_to_upper(schema: dict) -> dict:
    """Convert JSON-Schema types (lowercase) to genai-compatible uppercase."""
    out = {}
    if "type" in schema:
        out["type"] = schema["type"].upper()
    if "description" in schema:
        out["description"] = schema["description"]
    if "properties" in schema:
        out["properties"] = {k: _json_type_to_upper(v) for k, v in schema["properties"].items()}
    if "required" in schema:
        out["required"] = schema["required"]
    return out


def build_gemini_tools() -> list[Any] | None:
    """
    Build Gemini SDK Tool objects from _TOOL_DEFS.
    Targets google-genai (new SDK).  Returns None if SDK unavailable.
    """
    try:
        from google.genai import types as genai_types

        declarations = []
        for td in _TOOL_DEFS:
            params_dict = _json_type_to_upper(td["parameters"])
            declarations.append(
                genai_types.FunctionDeclaration(
                    name=td["name"],
                    description=td["description"],
                    parameters=params_dict,
                )
            )
        tool = genai_types.Tool(function_declarations=declarations)
        logger.debug("GeminiToolRegistry: built %d function declarations", len(declarations))
        return [tool]

    except ImportError:
        logger.debug("GeminiToolRegistry: google-genai not installed — tools unavailable")
        return None
    except Exception as exc:
        logger.warning("GeminiToolRegistry: build_gemini_tools failed — %s", exc)
        return None


# Module-level constant — None if SDK not installed or build failed
EIDOLON_TOOLS: list[Any] | None = build_gemini_tools()
