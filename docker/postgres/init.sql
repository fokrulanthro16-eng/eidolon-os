-- EIDOLON OS — PostgreSQL initialization
-- Runs once on first container start

-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Memory Records ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS memory_records (
    id               UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_type      VARCHAR(32) NOT NULL,
    source_path      TEXT,
    source_app       VARCHAR(255),
    window_title     VARCHAR(512),
    file_hash        VARCHAR(64),
    raw_text         TEXT,
    visual_summary   TEXT,
    chunk_count      INTEGER     DEFAULT 0,
    ocr_confidence   FLOAT,
    thumbnail_path   TEXT,
    metadata         JSONB       DEFAULT '{}'
);

-- ── Memory Chunks (vectors) ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS memory_chunks (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    record_id   UUID        NOT NULL REFERENCES memory_records(id) ON DELETE CASCADE,
    chunk_index INTEGER     NOT NULL,
    chunk_text  TEXT        NOT NULL,
    embedding   vector(1024),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Capture Events ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS capture_events (
    id               BIGSERIAL   PRIMARY KEY,
    captured_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    success          BOOLEAN     DEFAULT TRUE,
    memory_record_id UUID        REFERENCES memory_records(id) ON DELETE SET NULL,
    error_message    TEXT,
    duration_ms      INTEGER,
    source_app       VARCHAR(255),
    window_title     VARCHAR(512)
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

-- HNSW vector index (best recall/speed at scale)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON memory_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_chunks_record_id   ON memory_chunks (record_id);
CREATE INDEX IF NOT EXISTS idx_records_created_at ON memory_records (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_records_source_type ON memory_records (source_type);
CREATE INDEX IF NOT EXISTS idx_records_file_hash   ON memory_records (file_hash);
CREATE INDEX IF NOT EXISTS idx_capture_time        ON capture_events (captured_at DESC);

-- Full-text search (combined raw_text + visual_summary)
CREATE INDEX IF NOT EXISTS idx_records_fts ON memory_records
    USING gin(
        to_tsvector('english',
            COALESCE(raw_text, '') || ' ' || COALESCE(visual_summary, '')
        )
    );

CREATE INDEX IF NOT EXISTS idx_chunks_fts ON memory_chunks
    USING gin(to_tsvector('english', chunk_text));
