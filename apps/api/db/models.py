"""
SQLAlchemy ORM models backed by PostgreSQL + pgvector.
Mirrors the schema in docker/postgres/init.sql exactly.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMPTZ, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.db.database import Base

try:
    from pgvector.sqlalchemy import Vector
    _VECTOR_TYPE = Vector(1024)
except ImportError:
    # Graceful degradation — vector search won't work, but app boots
    from sqlalchemy import LargeBinary
    _VECTOR_TYPE = LargeBinary  # type: ignore


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class MemoryRecord(Base):
    __tablename__ = "memory_records"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, default=_now, nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_app: Mapped[str | None] = mapped_column(String(255), nullable=True)
    window_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict
    )

    chunks: Mapped[list["MemoryChunk"]] = relationship(
        back_populates="record",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        Index("idx_records_source_type", "source_type"),
        Index("idx_records_created_source", "created_at", "source_type"),
    )


class MemoryChunk(Base):
    __tablename__ = "memory_chunks"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    record_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("memory_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    # embedding stored in PostgreSQL via pgvector
    # Raw column — bypassing ORM type for pgvector compatibility
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=_now)

    record: Mapped["MemoryRecord"] = relationship(back_populates="chunks")


class CaptureEvent(Base):
    __tablename__ = "capture_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    captured_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, default=_now, nullable=False, index=True
    )
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    memory_record_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("memory_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_app: Mapped[str | None] = mapped_column(String(255), nullable=True)
    window_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
