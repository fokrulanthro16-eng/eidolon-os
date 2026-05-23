"""
Temporal Memory Graph — links memories by time, app, session, topic, and type.

All computation is local and CPU-only.  Semantic similarity edges are added
when sentence-transformers embeddings are available but are never required.

Graph format
------------
{
  "nodes": [{ id, type, title, source, created_at }],
  "edges": [{ from, to, relationship, confidence, reason }],
  "stats": { node_count, edge_count, relationships: {rel: count}, ... }
}

Relationships
-------------
same_session      — share a session_id
near_time         — captured within TIME_WINDOW_MINUTES of each other
same_app          — same app_name in metadata
same_topic        — 3+ keyword tokens in common
same_source_type  — same memory type (screenshot/pdf/voice/video/…)
workflow_related  — share a non-trivial workflow_type
semantic_match    — cosine similarity ≥ SEMANTIC_THRESHOLD (optional)
"""

import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Tuning constants
TIME_WINDOW_MINUTES = 30
TOPIC_MIN_SHARED    = 3     # min shared keywords for same_topic edge
MAX_OVERVIEW_NODES  = 120   # cap for overview graph
MAX_EDGES_PER_NODE  = 8     # prevent star-graph explosion
SEMANTIC_THRESHOLD  = 0.70  # cosine similarity floor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOISE = frozenset({
    "the","and","for","that","this","with","from","are","was","were","have","has",
    "been","will","would","could","should","can","may","might","shall","not","but",
    "also","just","like","into","onto","over","under","about","there","their",
    "they","then","than","when","where","which","who","what","how","why","its",
    "each","more","some","all","any","our","your","you","she","her","his","him",
})


def _parse_dt(iso: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.replace(tzinfo=timezone.utc) if not dt.tzinfo else dt
    except Exception:
        return None


def _keywords(text: str, n: int = 10) -> set[str]:
    freq: Counter = Counter()
    for w in re.findall(r"[a-zA-Z]{4,}", text.lower()):
        if w not in _NOISE:
            freq[w] += 1
    return {w for w, _ in freq.most_common(n)}


def _node(m: dict) -> dict:
    return {
        "id":         m["id"],
        "type":       m.get("type", "unknown"),
        "title":      m.get("title", "")[:80],
        "source":     m.get("source", ""),
        "created_at": m.get("created_at", ""),
    }


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na  = sum(x * x for x in a) ** 0.5
    nb  = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


# ---------------------------------------------------------------------------
# Edge builders — each returns a list of (from_id, to_id, rel, conf, reason)
# ---------------------------------------------------------------------------

def _session_edges(memories: list[dict]) -> list[tuple]:
    sess_to_ids: dict[str, list[str]] = defaultdict(list)
    for m in memories:
        sid = m.get("session_id")
        if sid:
            sess_to_ids[sid].append(m["id"])

    edges = []
    for sid, ids in sess_to_ids.items():
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                if j - i > MAX_EDGES_PER_NODE:
                    break
                edges.append((ids[i], ids[j], "same_session", 0.95,
                               f"Both in session {sid[:8]}"))
    return edges


def _time_edges(memories: list[dict]) -> list[tuple]:
    timed = [(m["id"], _parse_dt(m.get("created_at", ""))) for m in memories]
    timed = [(mid, dt) for mid, dt in timed if dt]
    timed.sort(key=lambda x: x[1])

    window = TIME_WINDOW_MINUTES * 60
    edges = []
    for i in range(len(timed)):
        count = 0
        for j in range(i + 1, len(timed)):
            diff = (timed[j][1] - timed[i][1]).total_seconds()
            if diff > window:
                break
            if count >= MAX_EDGES_PER_NODE:
                break
            edges.append((timed[i][0], timed[j][0], "near_time", 0.70,
                           f"Within {int(diff // 60)} min of each other"))
            count += 1
    return edges


def _app_edges(memories: list[dict]) -> list[tuple]:
    app_to_ids: dict[str, list[str]] = defaultdict(list)
    for m in memories:
        app = (m.get("metadata") or {}).get("app_name")
        if app:
            app_to_ids[app].append(m["id"])

    edges = []
    for app, ids in app_to_ids.items():
        if len(ids) < 2:
            continue
        for i in range(min(len(ids), 10)):
            for j in range(i + 1, min(len(ids), 10)):
                edges.append((ids[i], ids[j], "same_app", 0.80,
                               f"Both in {app}"))
    return edges


def _topic_edges(memories: list[dict]) -> list[tuple]:
    kw_map = {}
    for m in memories:
        text = (m.get("title", "") + " " + m.get("text", ""))[:500]
        kw_map[m["id"]] = _keywords(text)

    ids = list(kw_map.keys())
    edges = []
    for i in range(len(ids)):
        count = 0
        for j in range(i + 1, len(ids)):
            shared = kw_map[ids[i]] & kw_map[ids[j]]
            if len(shared) >= TOPIC_MIN_SHARED:
                conf = min(0.50 + 0.05 * len(shared), 0.90)
                kw_preview = ", ".join(sorted(shared)[:3])
                edges.append((ids[i], ids[j], "same_topic", conf,
                               f"Shared keywords: {kw_preview}"))
                count += 1
                if count >= MAX_EDGES_PER_NODE:
                    break
    return edges


def _workflow_edges(memories: list[dict]) -> list[tuple]:
    wf_to_ids: dict[str, list[str]] = defaultdict(list)
    trivial = {"unknown", "other", ""}
    for m in memories:
        wf = (m.get("metadata") or {}).get("workflow_type", "")
        if wf and wf not in trivial:
            wf_to_ids[wf].append(m["id"])

    edges = []
    for wf, ids in wf_to_ids.items():
        if len(ids) < 2:
            continue
        for i in range(min(len(ids), 10)):
            for j in range(i + 1, min(len(ids), 10)):
                edges.append((ids[i], ids[j], "workflow_related", 0.75,
                               f"Both in workflow: {wf}"))
    return edges


def _semantic_edges(memories: list[dict]) -> list[tuple]:
    """Optional cosine similarity edges using stored embeddings."""
    embedded = [(m["id"], m["embedding"]) for m in memories if m.get("embedding")]
    if len(embedded) < 2:
        return []

    edges = []
    for i in range(len(embedded)):
        count = 0
        for j in range(i + 1, len(embedded)):
            sim = _cosine(embedded[i][1], embedded[j][1])
            if sim >= SEMANTIC_THRESHOLD:
                edges.append((embedded[i][0], embedded[j][0], "semantic_match",
                               round(sim, 3), f"Semantic similarity {sim:.0%}"))
                count += 1
                if count >= MAX_EDGES_PER_NODE:
                    break
    return edges


# ---------------------------------------------------------------------------
# Graph assembler
# ---------------------------------------------------------------------------

def _build_graph(memories: list[dict], include_semantic: bool = True) -> dict[str, Any]:
    if not memories:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}}

    id_set = {m["id"] for m in memories}
    nodes  = [_node(m) for m in memories]

    raw_edges: list[tuple] = []
    raw_edges.extend(_session_edges(memories))
    raw_edges.extend(_time_edges(memories))
    raw_edges.extend(_app_edges(memories))
    raw_edges.extend(_topic_edges(memories))
    raw_edges.extend(_workflow_edges(memories))
    if include_semantic:
        try:
            raw_edges.extend(_semantic_edges(memories))
        except Exception as exc:
            logger.debug("semantic edges skipped: %s", exc)

    # Deduplicate and keep only edges whose both nodes are in the set
    seen: set[frozenset] = set()
    edges = []
    rel_counts: Counter = Counter()
    for (f, t, rel, conf, reason) in raw_edges:
        if f not in id_set or t not in id_set:
            continue
        key = frozenset({f, t, rel})
        if key in seen:
            continue
        seen.add(key)
        edges.append({"from": f, "to": t, "relationship": rel,
                       "confidence": conf, "reason": reason})
        rel_counts[rel] += 1

    stats: dict[str, Any] = {
        "node_count":     len(nodes),
        "edge_count":     len(edges),
        "relationships":  dict(rel_counts),
    }

    return {"nodes": nodes, "edges": edges, "stats": stats}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_overview_graph(memories: list[dict]) -> dict[str, Any]:
    """Graph of the most recent MAX_OVERVIEW_NODES memories."""
    recent = memories[-MAX_OVERVIEW_NODES:] if len(memories) > MAX_OVERVIEW_NODES else memories
    return _build_graph(recent, include_semantic=False)


def build_memory_graph(memory_id: str, memories: list[dict]) -> dict[str, Any]:
    """
    Ego-graph centred on memory_id: the memory itself plus all its 1-hop neighbours.
    Returns at most ~30 nodes.
    """
    target = next((m for m in memories if m["id"] == memory_id), None)
    if target is None:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}}

    # Find candidate neighbours via all relationship types
    full = _build_graph(memories, include_semantic=True)
    neighbour_ids = {memory_id}
    for e in full["edges"]:
        if e["from"] == memory_id:
            neighbour_ids.add(e["to"])
        elif e["to"] == memory_id:
            neighbour_ids.add(e["from"])

    subgraph_memories = [m for m in memories if m["id"] in neighbour_ids][:30]
    graph = _build_graph(subgraph_memories, include_semantic=True)
    graph["center_id"] = memory_id
    return graph


def build_session_graph(session_id: str, memories: list[dict]) -> dict[str, Any]:
    """Graph for all memories that belong to a given session."""
    session_mems = [m for m in memories if m.get("session_id") == session_id]
    if not session_mems:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0},
                "session_id": session_id, "memory_count": 0}
    graph = _build_graph(session_mems, include_semantic=True)
    graph["session_id"]    = session_id
    graph["memory_count"]  = len(session_mems)
    return graph
