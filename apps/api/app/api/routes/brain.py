"""
Brain Status + Chat endpoints — Phase 18.

GET  /brain/status   — current brain provider and availability
POST /brain/chat     — chat grounded in memories, using active brain
POST /brain/reset    — force re-probe (e.g. after starting Ollama/LM Studio)

Default provider: local_semantic (zero dependencies, always works).
Optional: set BRAIN_PROVIDER=ollama or BRAIN_PROVIDER=lmstudio in .env.
Falls back to local_semantic if the chosen provider is unreachable.
"""

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/brain", tags=["brain"])


class BrainChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: Optional[list[dict]] = None


@router.get("/status", summary="Current brain provider and availability")
async def brain_status():
    """
    Returns the active brain mode, provider, and whether LLM is live.

    brain_provider: local_semantic | ollama | lmstudio
    mode:           local_semantic | local_llm
    llm_active:     true if a local LLM is reachable
    fallback_used:  true if provider ≠ local_semantic but LLM unavailable
    """
    from app.services.llm.brain_router import get_brain_status
    return get_brain_status()


@router.post("/chat", summary="Chat with active brain, grounded in local memories")
async def brain_chat(req: BrainChatRequest):
    """
    Answers a question using the active brain, with memory context injected.

    - Searches memories for relevant context
    - Passes context to local_semantic / Ollama / LM Studio
    - Always returns an answer (fallback to local_semantic if LLM unavailable)
    - answer is grounded in actual stored memories
    """
    from app.services.llm.brain_router import get_active_brain
    from app.services.llm.memory_context import build_memory_context
    from app.services.memory_store import memory_store
    from app.services.search_service import search_memories

    brain     = get_active_brain()
    memories  = memory_store.list()
    matches   = search_memories(req.message.strip(), memories)[:8]
    context   = build_memory_context(
        user_message  = req.message,
        query_used    = req.message,
        raw_matches   = matches,
        time_filtered = False,
        all_items     = memories,
    )
    answer = brain.generate_with_history(req.message, context, req.history or [])
    return {
        "answer":        answer,
        "brain_mode":    brain.mode().value,
        "llm_active":    brain.is_llm_active(),
        "fallback_used": not brain.is_llm_active(),
        "sources_count": len(matches),
    }


@router.post("/reset", summary="Re-probe the brain provider")
async def brain_reset():
    """
    Force the brain router to re-probe the configured provider.
    Useful after starting Ollama or LM Studio without restarting the API.
    """
    from app.services.llm.brain_router import get_active_brain, reset_active_brain
    reset_active_brain()
    brain = get_active_brain()
    return {
        "message":    "Brain re-probed.",
        "mode":       brain.mode().value,
        "llm_active": brain.is_llm_active(),
    }
