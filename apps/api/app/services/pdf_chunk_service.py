"""
PDF chunk service — splits stored PDF text into overlapping chunks and retrieves
the most relevant ones for a query.

Chunk dict schema
-----------------
    chunk_id   str              — "{memory_id}__p{page}__c{index}"
    memory_id  str              — parent memory item id
    page_num   int              — 1-based page number (0 = preamble / unknown)
    text       str              — chunk text (may include leading overlap)
    embedding  list[float]|None — filled lazily on first get_chunks() call

Retrieval weights
-----------------
    semantic mode : 0.70 × cosine_sim  +  0.30 × keyword_overlap
    keyword mode  : keyword_overlap only
"""

import hashlib
import logging
import re

logger = logging.getLogger(__name__)

_CHUNK_MAX = 1_100   # target upper limit in chars
_CHUNK_MIN =   200   # don't emit chunks smaller than this
_OVERLAP   =   150   # chars carried forward from previous chunk as context
_DEDUP_LEN =    60   # fingerprint window for near-duplicate detection

_PAGE_RE = re.compile(r"\[Page (\d+)\]")

# In-memory chunk cache: memory_id → list[chunk_dict]
_chunk_cache: dict[str, list[dict]] = {}


def _fingerprint(text: str) -> str:
    """Short hash of the first _DEDUP_LEN chars for near-duplicate detection."""
    return hashlib.md5(text[:_DEDUP_LEN].lower().strip().encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> list[str]:
    """
    Lightweight sentence splitter — no NLP dependencies.
    Splits on:
      - .!? followed by whitespace + capital letter
      - Newlines (treated as soft sentence boundaries)
    """
    # First split on hard newlines to respect paragraph structure
    lines = text.splitlines()
    sentences: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Further split long lines at sentence boundaries
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'\(])", line)
        sentences.extend(p.strip() for p in parts if p.strip())
    return sentences or [text]


def _page_chunks(page_num: int, text: str, memory_id: str, start_idx: int) -> list[dict]:
    """Split one page's text into overlapping chunks. Returns chunk dicts (no embeddings)."""
    sentences = _split_sentences(text) or [text]
    chunks: list[dict] = []
    current: list[str] = []
    current_len = 0
    overlap_tail = ""

    for sent in sentences:
        if current_len + len(sent) + 1 > _CHUNK_MAX and current:
            body = " ".join(current)
            chunks.append({
                "chunk_id":  f"{memory_id}__p{page_num}__c{start_idx + len(chunks)}",
                "memory_id": memory_id,
                "page_num":  page_num,
                "text":      (overlap_tail + body).strip(),
                "embedding": None,
            })
            overlap_tail = (body[-_OVERLAP:] + " ") if len(body) > _OVERLAP else (body + " ")
            current = []
            current_len = 0

        current.append(sent)
        current_len += len(sent) + 1

    if current:
        body = " ".join(current)
        if len(body) >= _CHUNK_MIN or not chunks:
            chunks.append({
                "chunk_id":  f"{memory_id}__p{page_num}__c{start_idx + len(chunks)}",
                "memory_id": memory_id,
                "page_num":  page_num,
                "text":      (overlap_tail + body).strip(),
                "embedding": None,
            })

    return chunks


_SKIP_MARKERS = ("[scanned image", "[empty]", "[… text truncated", "[PDF stored")


def parse_chunks(memory_id: str, full_text: str) -> list[dict]:
    """
    Parse "[Page N]\\ntext…" format into a flat list of chunk dicts.
    Falls back to chunking the whole text if no [Page N] markers exist.
    """
    segments = _PAGE_RE.split(full_text)
    chunks: list[dict] = []

    # Preamble text before the first [Page N]
    preamble = segments[0].strip()
    if len(preamble) >= _CHUNK_MIN:
        chunks += _page_chunks(0, preamble, memory_id, 0)

    # Alternating: page_number_str, text_block
    i = 1
    while i + 1 <= len(segments) - 1:
        try:
            page_num = int(segments[i])
        except (ValueError, IndexError):
            i += 2
            continue

        text_block = segments[i + 1].strip()
        if text_block and not any(text_block.startswith(m) for m in _SKIP_MARKERS):
            chunks += _page_chunks(page_num, text_block, memory_id, len(chunks))
        i += 2

    # Fallback: no [Page N] markers found
    if not chunks and len(full_text.strip()) >= _CHUNK_MIN:
        chunks += _page_chunks(1, full_text.strip(), memory_id, 0)

    # Deduplicate near-identical chunks (e.g. repeated headers/footers)
    seen_fps: set[str] = set()
    deduped: list[dict] = []
    for chunk in chunks:
        fp = _fingerprint(chunk["text"])
        if fp not in seen_fps:
            seen_fps.add(fp)
            deduped.append(chunk)
        else:
            logger.debug("Dropped duplicate chunk %s", chunk["chunk_id"])

    return deduped


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def _embed_chunks(chunks: list[dict]) -> None:
    """Embed all un-embedded chunks in one batch call. Mutates in-place. Non-fatal."""
    from app.services.embedding_service import embedding_service
    if not embedding_service.is_available():
        return

    todo = [c for c in chunks if c["embedding"] is None]
    if not todo:
        return

    texts = [c["text"][:512] for c in todo]
    vecs  = embedding_service.embed_batch(texts)
    for chunk, vec in zip(todo, vecs):
        chunk["embedding"] = vec


def get_chunks(memory_id: str, full_text: str) -> list[dict]:
    """Return (and lazily cache) chunks for a PDF memory item."""
    if memory_id not in _chunk_cache:
        chunks = parse_chunks(memory_id, full_text)
        _embed_chunks(chunks)
        _chunk_cache[memory_id] = chunks
    return _chunk_cache[memory_id]


def invalidate_cache(memory_id: str) -> None:
    """Remove cached chunks (call when a PDF memory is deleted)."""
    _chunk_cache.pop(memory_id, None)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def _keyword_score(query: str, text: str) -> float:
    """Normalised word-overlap score in [0, 1]."""
    q_words = set(re.findall(r"\w+", query.lower()))
    t_words = set(re.findall(r"\w+", text.lower()))
    if not q_words:
        return 0.0
    return len(q_words & t_words) / len(q_words)


def retrieve_chunks(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    """
    Score chunks against query. Returns top_k dicts with an added "score" field.
    Uses semantic + keyword when embeddings are available; keyword-only otherwise.
    """
    from app.services.embedding_service import embedding_service

    q_vec        = embedding_service.embed_query(query)
    use_semantic = q_vec is not None

    scored: list[dict] = []
    for chunk in chunks:
        if use_semantic and chunk.get("embedding"):
            sem = embedding_service.cosine_similarity(q_vec, chunk["embedding"])
        else:
            sem = 0.0
        kw    = _keyword_score(query, chunk["text"])
        score = (0.70 * sem + 0.30 * kw) if use_semantic else kw
        scored.append({**chunk, "score": score})

    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:top_k]
