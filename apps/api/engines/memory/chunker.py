"""
Text chunker with sliding window and sentence-boundary awareness.
Uses tiktoken for accurate token counting (same tokenizer as embedding models).
"""
import re


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def chunk_text(
    text: str,
    chunk_size: int = 400,
    overlap: int = 50,
    encoding_name: str = "cl100k_base",
) -> list[str]:
    if not text.strip():
        return []

    try:
        import tiktoken
        enc = tiktoken.get_encoding(encoding_name)

        def token_len(t: str) -> int:
            return len(enc.encode(t))

    except Exception:
        # Fallback: approximate by word count
        def token_len(t: str) -> int:
            return len(t.split())

    sentences = _split_sentences(text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sent in sentences:
        sent_len = token_len(sent)
        if current_len + sent_len > chunk_size and current:
            chunks.append(" ".join(current))
            # Carry overlap sentences forward
            overlap_sents: list[str] = []
            overlap_len = 0
            for s in reversed(current):
                l = token_len(s)
                if overlap_len + l > overlap:
                    break
                overlap_sents.insert(0, s)
                overlap_len += l
            current = overlap_sents
            current_len = overlap_len

        current.append(sent)
        current_len += sent_len

    if current:
        chunks.append(" ".join(current))

    return [c for c in chunks if c.strip()]
