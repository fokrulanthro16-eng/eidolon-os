"""
Chat router — Phase 4 Local LLM Brain.

Endpoints
---------
POST /chat/query       Non-streaming with session history
POST /chat/stream      SSE token-by-token streaming with session history
GET  /chat/sessions    List active sessions
DELETE /chat/sessions/{id}  Clear a session

SSE event format
----------------
Non-final: {"delta": "...", "done": false}
Final:     {"delta": "", "done": true, "session_id": "...", "sources": [...],
            "query_used": "...", "brain_mode": "...", "total_memories": N}
"""

import asyncio
import json
import logging
import threading
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.chat import ChatQueryRequest, ChatQueryResponse, ChatSource
from app.services.chat_memory_service import (
    _apply_temporal_filter,
    extract_search_terms,
    extract_temporal_filter,
)
from app.services.chat_session import chat_session_store
from app.services.llm.brain_router import get_active_brain
from app.services.llm.memory_context import build_memory_context
from app.services.memory_store import memory_store
from app.services.search_service import search_memories

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

_TOP_N = 8

# Phrases that signal the user wants pattern inference or a profile summary,
# not a keyword lookup.  For these we always load recent memories regardless
# of whether the keyword search returned anything.
_REASONING_PATTERNS: frozenset[str] = frozenset({
    "who am i", "who are you", "what am i", "who i am",
    "what patterns", "what do you see", "what do you know about me",
    "what can you tell", "what can you infer",
    "summarize", "summary", "recent activity",
    "based on my memories", "based on the memories",
    "tell me about me", "tell me about my",
    "describe me", "my activity", "my work", "my habits",
    "my profile", "my history", "what have i been",
    # Identity questions
    "what am i building", "active projects", "what should i work on",
    "work on next", "what should i focus", "what are my projects",
})


def _is_reasoning_query(message: str) -> bool:
    """True for broad identity / pattern / summary questions."""
    m = message.lower()
    return any(p in m for p in _REASONING_PATTERNS)


def _brain_mode_label(raw: str) -> str:
    """Normalise BrainMode enum values to UI-facing strings.

    brain_router returns REMOTE_LLM for Gemini; rename it so the frontend
    ChatBubble shows "gemini_hybrid" consistently with /brain/chat.
    """
    return "gemini_hybrid" if raw == "remote_llm" else raw


# ---------------------------------------------------------------------------
# Shared retrieval pipeline
# ---------------------------------------------------------------------------

def _recall(message: str) -> tuple[str, list[dict], dict]:
    """
    Run the full memory retrieval pipeline.
    Returns (query_used, raw_matches, context_dict).

    Enrichment rules
    ----------------
    1. Reasoning / profile queries ("Who am I?", "What patterns?", etc.)
       always get the most recent _TOP_N memories merged in, so Gemini can
       infer patterns even when keyword search returns nothing.
    2. When keyword search returns zero results for any query, recent
       memories are loaded as a fallback so Gemini always has context.
    """
    query = extract_search_terms(message)
    time_start, time_end = extract_temporal_filter(message)
    time_filtered = time_start is not None

    all_items = memory_store.list()
    raw_matches = search_memories(query=query, items=all_items)

    if time_filtered:
        raw_matches = _apply_temporal_filter(raw_matches, time_start, time_end)

    # Enrich with recent memories for reasoning queries OR when search found nothing.
    # This ensures "Who am I?", "What patterns do you see?", "Summarize my activity"
    # always produce real Gemini reasoning instead of "found nothing" responses.
    if not raw_matches or _is_reasoning_query(message):
        recent = sorted(
            all_items,
            key=lambda x: x.get("created_at", ""),
            reverse=True,
        )[:_TOP_N]
        seen_ids = {m["item"].get("id") for m in raw_matches}
        for item in recent:
            if item.get("id") not in seen_ids and len(raw_matches) < _TOP_N:
                raw_matches.append({
                    "item":           item,
                    "score":          0.5,
                    "semantic_score": 0.5,
                })
                seen_ids.add(item.get("id"))

    context = build_memory_context(
        user_message=message,
        query_used=query,
        raw_matches=raw_matches,
        time_filtered=time_filtered,
        time_start=time_start,
        time_end=time_end,
        all_items=all_items,
    )

    # For reasoning / identity queries, inject identity context so Gemini
    # can give specific answers about active projects, goals, and focus.
    if _is_reasoning_query(message):
        try:
            from app.services.identity_service import get_or_build as _ident_build
            context["identity"] = _ident_build(all_items)
        except Exception as exc:
            logger.debug("chat: identity context unavailable — %s", exc)

    return query, raw_matches, context


def _build_sources(raw_matches: list[dict]) -> list[ChatSource]:
    return [
        ChatSource(
            id=m["item"].get("id", ""),
            title=m["item"].get("title", ""),
            source=m["item"].get("source", ""),
            type=m["item"].get("type", ""),
            created_at=m["item"].get("created_at", ""),
            score=round(float(m["score"]), 2),
            semantic_score=round(float(m.get("semantic_score", 0)), 4),
        )
        for m in raw_matches[:_TOP_N]
    ]


# ---------------------------------------------------------------------------
# Non-streaming endpoint
# ---------------------------------------------------------------------------

@router.post("/query", response_model=ChatQueryResponse)
async def chat_query(body: ChatQueryRequest):
    """Full answer in one response with session history."""
    query, raw_matches, context = _recall(body.message)

    session  = chat_session_store.get_or_create(body.session_id)
    history  = chat_session_store.get_history(session.session_id, n=8)
    brain    = get_active_brain()
    answer   = brain.generate_with_history(body.message, context, history)
    mode     = _brain_mode_label(brain.mode().value)

    chat_session_store.add_message(session.session_id, "user", body.message)
    chat_session_store.add_message(session.session_id, "assistant", answer)

    logger.info(
        "chat/query: session=%s brain=%s matches=%d",
        session.session_id, mode, len(raw_matches),
    )

    return ChatQueryResponse(
        answer=answer,
        session_id=session.session_id,
        sources=_build_sources(raw_matches),
        query_used=query,
        brain_mode=mode,
        total_memories=len(raw_matches),
    )


# ---------------------------------------------------------------------------
# Streaming endpoint
# ---------------------------------------------------------------------------

@router.post("/stream")
async def chat_stream(body: ChatQueryRequest):
    """SSE streaming — yields text deltas then a final event with metadata."""

    # Do all blocking retrieval before the response starts
    query, raw_matches, context = _recall(body.message)
    session = chat_session_store.get_or_create(body.session_id)
    history = chat_session_store.get_history(session.session_id, n=8)
    brain   = get_active_brain()
    mode    = _brain_mode_label(brain.mode().value)

    collected_parts: list[str] = []

    async def _sse_generator() -> AsyncGenerator[str, None]:
        loop = asyncio.get_event_loop()
        # sentinel object signals the producer thread is done
        _DONE = object()
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)

        def _produce() -> None:
            try:
                for delta in brain.generate_stream(body.message, context, history):
                    collected_parts.append(delta)
                    asyncio.run_coroutine_threadsafe(
                        queue.put(delta), loop
                    ).result(timeout=60)
            except Exception as exc:
                logger.error("brain stream error: %s", exc)
            asyncio.run_coroutine_threadsafe(
                queue.put(_DONE), loop
            ).result(timeout=10)

        threading.Thread(target=_produce, name="brain-stream", daemon=True).start()

        while True:
            item = await asyncio.wait_for(queue.get(), timeout=120)
            if item is _DONE:
                break
            yield f"data: {json.dumps({'delta': item, 'done': False})}\n\n"

        # Persist to session history
        answer_text = "".join(collected_parts)
        chat_session_store.add_message(session.session_id, "user", body.message)
        chat_session_store.add_message(session.session_id, "assistant", answer_text)

        # Final event: metadata + source citations
        sources_data = [s.model_dump() for s in _build_sources(raw_matches)]
        done_payload = {
            "delta":          "",
            "done":           True,
            "session_id":     session.session_id,
            "sources":        sources_data,
            "query_used":     query,
            "brain_mode":     mode,
            "total_memories": len(raw_matches),
        }
        yield f"data: {json.dumps(done_payload)}\n\n"

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

@router.get("/sessions")
async def list_sessions():
    return {"sessions": chat_session_store.list_sessions()}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    if not chat_session_store.delete_session(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return {"success": True, "deleted_id": session_id}
