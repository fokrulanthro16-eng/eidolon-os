"""
pgvector adapter for semantic memory search.

Design principles:
- Raw asyncpg calls for vector operations (SQLAlchemy doesn't express vector ops natively)
- Hybrid search ready: add FTS re-ranking in Phase 2 via RRF
- All vector dims are 1024 (BGE-M3). Change VECTOR_DIM to switch models.
- HNSW index used at DB level (see init.sql) — query is always fast
"""
import logging
from typing import Any

import asyncpg

from apps.api.config import settings

logger = logging.getLogger(__name__)

VECTOR_DIM = 1024  # BGE-M3. Switch to 384 for BGE-small.


async def _get_conn() -> asyncpg.Connection:
    """Get a raw asyncpg connection for vector operations."""
    # Extract DSN from SQLAlchemy URL (swap driver prefix)
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    return conn


async def upsert_chunks(
    record_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
    source_type: str,
    source_app: str | None,
    window_title: str | None,
) -> int:
    if not chunks:
        return 0

    conn = await _get_conn()
    try:
        await conn.execute("SET LOCAL synchronous_commit = off")  # perf: async commit

        for i, (text, vec) in enumerate(zip(chunks, embeddings)):
            vec_str = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
            await conn.execute(
                """
                INSERT INTO memory_chunks (record_id, chunk_index, chunk_text, embedding)
                VALUES ($1, $2, $3, $4::vector)
                ON CONFLICT DO NOTHING
                """,
                record_id, i, text, vec_str,
            )
        return len(chunks)
    finally:
        await conn.close()


async def semantic_search(
    query_embedding: list[float],
    top_k: int = 10,
    source_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    conn = await _get_conn()
    try:
        vec_str = "[" + ",".join(f"{v:.6f}" for v in query_embedding) + "]"

        # Build WHERE clause dynamically
        conditions = []
        params: list[Any] = [vec_str, top_k]
        pidx = 3

        if source_type:
            conditions.append(f"r.source_type = ${pidx}")
            params.append(source_type)
            pidx += 1
        if date_from:
            conditions.append(f"r.created_at >= ${pidx}::timestamptz")
            params.append(date_from)
            pidx += 1
        if date_to:
            conditions.append(f"r.created_at <= ${pidx}::timestamptz")
            params.append(date_to)
            pidx += 1

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        rows = await conn.fetch(
            f"""
            SELECT
                r.id           AS record_id,
                r.source_type,
                r.source_app,
                r.window_title,
                r.created_at,
                r.thumbnail_path,
                r.visual_summary,
                c.chunk_text,
                1 - (c.embedding <=> $1::vector) AS score
            FROM memory_chunks c
            JOIN memory_records r ON r.id = c.record_id
            {where_clause}
            ORDER BY c.embedding <=> $1::vector
            LIMIT $2
            """,
            *params,
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def delete_record_vectors(record_id: str) -> None:
    conn = await _get_conn()
    try:
        await conn.execute(
            "DELETE FROM memory_chunks WHERE record_id = $1", record_id
        )
    finally:
        await conn.close()


async def count_chunks() -> int:
    conn = await _get_conn()
    try:
        row = await conn.fetchrow("SELECT COUNT(*) FROM memory_chunks")
        return row[0] if row else 0
    finally:
        await conn.close()
