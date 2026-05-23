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
from app.services.llm import get_brain
from app.services.llm.memory_context import build_memory_context
from app.services.memory_store import memory_store
from app.services.search_service import search_memories

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

_TOP_N = 8


# ---------------------------------------------------------------------------
# Shared retrieval pipeline
# ---------------------------------------------------------------------------

def _recall(message: str) -> tuple[str, list[dict], dict]:
    """
    Run the full memory retrieval pipeline.
    Returns (query_used, raw_matches, context_dict).
    """
    query = extract_search_terms(message)
    time_start, time_end = extract_temporal_filter(message)
    time_filtered = time_start is not None

    all_items = memory_store.list()
    raw_matches = search_memories(query=query, items=all_items)

    if time_filtered:
        raw_matches = _apply_temporal_filter(raw_matches, time_start, time_end)

    context = build_memory_context(
        user_message=message,
        query_used=query,
        raw_matches=raw_matches,
        time_filtered=time_filtered,
        time_start=time_start,
        time_end=time_end,
        all_items=all_items,
    )
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
    brain    = get_brain()
    answer   = brain.generate_with_history(body.message, context, history)

    chat_session_store.add_message(session.session_id, "user", body.message)
    chat_session_store.add_message(session.session_id, "assistant", answer)

    logger.info(
        "chat/query: session=%s brain=%s matches=%d",
        session.session_id, brain.mode().value, len(raw_matches),
    )

    return ChatQueryResponse(
        answer=answer,
        session_id=session.session_id,
        sources=_build_sources(raw_matches),
        query_used=query,
        brain_mode=brain.mode().value,
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
    brain   = get_brain()

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
                logger.error("Ollama stream error: %s", exc)
            asyncio.run_coroutine_threadsafe(
                queue.put(_DONE), loop
            ).result(timeout=10)

        threading.Thread(target=_produce, name="ollama-stream", daemon=True).start()

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
            "brain_mode":     brain.mode().value,
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
