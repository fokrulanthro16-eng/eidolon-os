"""
BGE-M3 embedding engine.

BGE-M3 advantages over BGE-small for EIDOLON OS:
- 1024-dim vectors (vs 384) — higher information density
- Multilingual: 100+ languages — future-proof for global users
- Better recall on short UI snippets (button labels, code identifiers)
- ColBERT-style late interaction available in FlagEmbedding (Phase 3)

First run: auto-downloads ~570MB model from HuggingFace.
Subsequent runs: loads from cache in ~3s.
"""
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# BGE-M3 query instruction (improves retrieval precision by ~8%)
_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class EmbeddingEngine:
    def __init__(self, model_name: str, device: str = "cpu", batch_size: int = 32) -> None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading %s on %s ...", model_name, device)
        self._model = SentenceTransformer(model_name, device=device)
        self._device = device
        self._batch_size = batch_size
        logger.info("Embedding engine ready. Dim=%d", self._model.get_sentence_embedding_dimension())

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vecs = self._model.encode(
            texts,
            normalize_embeddings=True,      # L2-normalize for cosine similarity
            batch_size=self._batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return vecs.tolist()

    def embed_query(self, query: str) -> list[float]:
        """Apply query instruction prefix for BGE-M3 asymmetric retrieval."""
        prefixed = _QUERY_INSTRUCTION + query
        return self.embed([prefixed])[0]

    def embed_passages(self, passages: list[str]) -> list[list[float]]:
        """Passage embedding — no prefix, higher throughput."""
        return self.embed(passages)

    @property
    def dimension(self) -> int:
        return self._model.get_sentence_embedding_dimension()


@lru_cache(maxsize=1)
def get_embedder() -> EmbeddingEngine:
    from apps.api.config import settings
    return EmbeddingEngine(
        model_name=settings.embed_model,
        device=settings.embed_device,
        batch_size=settings.embed_batch_size,
    )
