"""
Temporal Memory Graph endpoints.

GET /graph/overview              — graph of recent memories (up to 120 nodes)
GET /graph/memory/{memory_id}    — ego-graph centred on one memory
GET /graph/session/{session_id}  — graph for all memories in a session
"""

import logging

from fastapi import APIRouter, HTTPException

from app.services.memory_graph_service import (
    build_memory_graph,
    build_overview_graph,
    build_session_graph,
)
from app.services.memory_store import memory_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/overview", summary="Memory relationship graph (recent 120 memories)")
def graph_overview():
    """
    Returns nodes + edges for up to 120 recent memories.
    Edge types: same_session, near_time, same_app, same_topic, workflow_related.
    """
    memories = memory_store.list()
    graph = build_overview_graph(memories)
    return graph


@router.get("/memory/{memory_id}", summary="Ego-graph for a single memory")
def graph_for_memory(memory_id: str):
    """
    Returns the target memory and all its directly connected neighbours
    (up to 30 nodes), with all edges between them.
    """
    memories = memory_store.list()
    if not any(m["id"] == memory_id for m in memories):
        raise HTTPException(status_code=404, detail="Memory not found")
    graph = build_memory_graph(memory_id, memories)
    return graph


@router.get("/session/{session_id}", summary="Graph for all memories in a session")
def graph_for_session(session_id: str):
    """
    Returns all memories belonging to session_id as a connected graph.
    """
    memories = memory_store.list()
    graph = build_session_graph(session_id, memories)
    if graph.get("memory_count", 0) == 0:
        raise HTTPException(status_code=404, detail="Session not found or has no memories")
    return graph
