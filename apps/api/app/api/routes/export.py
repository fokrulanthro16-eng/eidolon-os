"""
Export router — download memories and sessions as JSON files.

Endpoints
---------
GET /export/memories   Download all memories as memories_YYYYMMDD_HHMMSS.json
GET /export/sessions   Download all sessions (with slim memories) as sessions_YYYYMMDD_HHMMSS.json

Embeddings are stripped from all exports — they are large (384 floats each)
and not useful outside the EIDOLON runtime.
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Response

from app.services.memory_store import memory_store
from app.services.session_service import detect_sessions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/export", tags=["export"])

_JSON_MIME = "application/json"


def _strip_embedding(item: dict) -> dict:
    return {k: v for k, v in item.items() if k != "embedding"}


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


@router.get("/memories")
async def export_memories():
    """
    Download all memories as a JSON file.
    Embeddings are excluded; all other fields preserved.
    """
    items = memory_store.list()
    clean = [_strip_embedding(it) for it in items]
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version":     "1.0",
        "count":       len(clean),
        "memories":    clean,
    }
    content  = json.dumps(payload, indent=2, ensure_ascii=False)
    filename = f"eidolon_memories_{_timestamp()}.json"

    logger.info("export/memories: %d items  (%d bytes)", len(clean), len(content))
    return Response(
        content=content,
        media_type=_JSON_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/sessions")
async def export_sessions():
    """
    Download all sessions with their memory items as a JSON file.
    Embeddings are stripped from each memory item.
    """
    items    = memory_store.list()
    sessions = detect_sessions(items)

    clean_sessions = []
    for s in sessions:
        slim_mems = [_strip_embedding(m) for m in s.get("memories", [])]
        clean_sessions.append({**s, "memories": slim_mems})

    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version":     "1.0",
        "count":       len(clean_sessions),
        "sessions":    clean_sessions,
    }
    content  = json.dumps(payload, indent=2, ensure_ascii=False)
    filename = f"eidolon_sessions_{_timestamp()}.json"

    logger.info("export/sessions: %d sessions  (%d bytes)", len(clean_sessions), len(content))
    return Response(
        content=content,
        media_type=_JSON_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
