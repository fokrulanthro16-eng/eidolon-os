"""
Semantic embedding service using sentence-transformers.

Gracefully degrades to keyword-only mode if the library is unavailable.
Thread-safe: model is loaded once under a lock.
"""

import logging
import threading
from collections import OrderedDict

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_QUERY_CACHE_MAX = 64


class EmbeddingService:
    def __init__(self) -> None:
        self._model = None
        self._load_lock = threading.Lock()
        self._available: bool | None = None  # None = not yet probed
        self._query_cache: OrderedDict[str, list[float]] = OrderedDict()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        if self._available is None:
            try:
                import sentence_transformers  # noqa: F401
                self._available = True
            except ImportError:
                self._available = False
                logger.info("sentence-transformers not installed — keyword search active.")
        return self._available

    def embed_query(self, query: str) -> list[float] | None:
        """
        Return a normalised embedding for a search query.
        Results are cached (LRU, max _QUERY_CACHE_MAX entries) to avoid
        re-encoding the same query string within a session.
        """
        if not self.is_available():
            return None
        key = query.strip()[:256]
        if key in self._query_cache:
            self._query_cache.move_to_end(key)
            return self._query_cache[key]
        vec = self._encode(key)
        if vec is not None:
            self._query_cache[key] = vec
            if len(self._query_cache) > _QUERY_CACHE_MAX:
                self._query_cache.popitem(last=False)
        return vec

    def embed_for_storage(self, title: str, text: str) -> list[float] | None:
        """
        Return a normalised 384-dim embedding for storage.
        Combines title (weighted) + text for richer representation.
        Returns None if the model is unavailable.
        """
        if not self.is_available():
            return None
        combined = f"{title} {title} {text}"[:1024]  # title repeated for weight
        return self._encode(combined)

    def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Encode a batch of strings. Returns a parallel list."""
        if not self.is_available():
            return [None] * len(texts)
        model = self._get_model()
        if model is None:
            return [None] * len(texts)
        try:
            import numpy as np
            vecs = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
            return [v.tolist() for v in vecs]
        except Exception as exc:
            logger.warning("embed_batch failed: %s", exc)
            return [None] * len(texts)

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """
        Cosine similarity between two normalised vectors.
        For unit vectors: dot(a, b) == cosine(a, b).
        Falls back to pure-Python dot product if numpy absent.
        """
        try:
            import numpy as np
            return float(np.dot(a, b))
        except ImportError:
            return sum(x * y for x, y in zip(a, b))

    def backfill_embeddings(self, memory_store) -> int:
        """
        Encode any stored items that lack an embedding.
        Runs in a background thread at startup — never blocks the API.
        Returns the number of items updated.
        """
        if not self.is_available():
            return 0

        items = memory_store.list_raw()
        missing = [it for it in items if not it.get("embedding")]
        if not missing:
            return 0

        logger.info("Backfilling embeddings for %d items…", len(missing))
        texts = [f"{it.get('title', '')} {it.get('title', '')} {it.get('text', '')} "[:1024] for it in missing]
        vecs = self.embed_batch(texts)

        updated = 0
        for item, vec in zip(missing, vecs):
            if vec is not None:
                memory_store.update_embedding(item["id"], vec)
                updated += 1

        logger.info("Backfill complete — %d/%d items embedded.", updated, len(missing))
        return updated

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_model(self):
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    logger.info("Loading embedding model %s…", _MODEL_NAME)
                    self._model = SentenceTransformer(_MODEL_NAME)
                    logger.info("Embedding model ready.")
                except Exception as exc:
                    logger.warning("Failed to load embedding model: %s", exc)
                    self._available = False
                    return None
        return self._model

    def _encode(self, text: str) -> list[float] | None:
        model = self._get_model()
        if model is None:
            return None
        try:
            vec = model.encode([text], normalize_embeddings=True, show_progress_bar=False)
            return vec[0].tolist()
        except Exception as exc:
            logger.warning("encode failed: %s", exc)
            return None


# Shared singleton
embedding_service = EmbeddingService()
