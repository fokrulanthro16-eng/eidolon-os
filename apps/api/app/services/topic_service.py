"""
Lightweight topic clustering for memory collections.

Two strategies — whichever is available:
  1. Embedding-based: simple k-means on stored 384-dim vectors (no new deps)
  2. Keyword/app fallback: group by app_name + keyword frequency

Returns [{label, keywords, memory_ids, count}] sorted by count descending.
Used by the /summary/daily endpoint to enrich daily reports.
"""

import logging
import math
import re
from collections import Counter
from typing import Any

from app.services.session_service import NOISE_WORDS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _words(text: str) -> list[str]:
    return [
        w for w in re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        if w not in NOISE_WORDS
    ]


def _top_words(texts: list[str], n: int = 6) -> list[str]:
    freq: Counter = Counter()
    for t in texts:
        for w in _words(t):
            freq[w] += 1
    return [w for w, _ in freq.most_common(n)]


def _label_from_words(words: list[str], n: int = 2) -> str:
    if not words:
        return "General"
    return " / ".join(w.title() for w in words[:n])


# ---------------------------------------------------------------------------
# Embedding-based k-means (pure-Python, no scipy/sklearn)
# ---------------------------------------------------------------------------

def _kmeans(vectors: list[list[float]], k: int, max_iter: int = 15) -> list[int]:
    """
    Assign each vector an integer cluster label 0..k-1.
    Uses cosine similarity (vectors assumed normalised).
    Returns list of assignments parallel to `vectors`.
    """
    if len(vectors) <= k:
        return list(range(len(vectors)))

    centroids = [list(v) for v in vectors[:k]]

    def dot(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b))

    def normalize(v: list[float]) -> list[float]:
        mag = math.sqrt(sum(x * x for x in v))
        return [x / mag for x in v] if mag > 0 else v

    assignments: list[int] = [0] * len(vectors)

    for _ in range(max_iter):
        # Assignment step
        new_assignments = []
        for vec in vectors:
            sims = [dot(vec, c) for c in centroids]
            new_assignments.append(sims.index(max(sims)))

        if new_assignments == assignments:
            break
        assignments = new_assignments

        # Update step
        for ci in range(k):
            members = [vectors[i] for i, a in enumerate(assignments) if a == ci]
            if not members:
                continue
            dim = len(members[0])
            avg = [sum(m[d] for m in members) / len(members) for d in range(dim)]
            centroids[ci] = normalize(avg)

    return assignments


def _embedding_clusters(memories: list[dict], n: int) -> list[dict] | None:
    """
    Try to cluster memories using stored embedding vectors.
    Returns None if embeddings unavailable or too few vectors.
    """
    try:
        from app.services.embedding_service import embedding_service
        if not embedding_service.is_available():
            return None

        vec_pairs = [(m["id"], m["embedding"]) for m in memories if m.get("embedding")]
        if len(vec_pairs) < max(n * 2, 4):
            return None

        k = min(n, max(2, int(math.sqrt(len(vec_pairs)))))
        ids     = [p[0] for p in vec_pairs]
        vectors = [p[1] for p in vec_pairs]

        assignments = _kmeans(vectors, k)

        mem_lookup = {m["id"]: m for m in memories}
        clusters: list[dict] = []
        for ci in range(k):
            cluster_ids = [ids[i] for i, a in enumerate(assignments) if a == ci]
            if not cluster_ids:
                continue
            cluster_mems = [mem_lookup[mid] for mid in cluster_ids if mid in mem_lookup]
            texts = [m.get("title", "") + " " + (m.get("text", "")[:200]) for m in cluster_mems]
            top = _top_words(texts)
            clusters.append({
                "label":      _label_from_words(top),
                "keywords":   top,
                "memory_ids": cluster_ids,
                "count":      len(cluster_ids),
            })

        clusters.sort(key=lambda x: -x["count"])
        return clusters

    except Exception as exc:
        logger.debug("Embedding clustering failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Keyword / app-name fallback clustering
# ---------------------------------------------------------------------------

def _app_clusters(memories: list[dict], n: int) -> list[dict]:
    """Group by app_name, then surface top keywords per group."""
    from collections import defaultdict
    groups: dict[str, list[dict]] = defaultdict(list)
    for m in memories:
        app = (m.get("metadata") or {}).get("app_name") or m.get("source") or "other"
        groups[app].append(m)

    clusters: list[dict] = []
    for app, mems in sorted(groups.items(), key=lambda x: -len(x[1])):
        texts = [m.get("title", "") + " " + (m.get("text", "")[:200]) for m in mems]
        top = _top_words(texts)
        clusters.append({
            "label":      app,
            "keywords":   top,
            "memory_ids": [m["id"] for m in mems],
            "count":      len(mems),
        })
        if len(clusters) >= n:
            break

    return clusters


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def cluster_memories(memories: list[dict], n_topics: int = 6) -> list[dict]:
    """
    Group memories into topic clusters.

    Tries embedding-based k-means first (no new deps — uses stored vectors).
    Falls back to app-name + keyword grouping if unavailable.

    Returns list of:
        {label, keywords, memory_ids, count}
    sorted by count descending.
    """
    if not memories:
        return []

    result = _embedding_clusters(memories, n_topics)
    if result:
        return result

    return _app_clusters(memories, n_topics)
