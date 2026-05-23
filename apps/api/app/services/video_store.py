"""
Thread-safe JSON store for video metadata and per-video event timelines.

Layout on disk
--------------
storage/video-db/
    video_index.json          — list of VideoRecord dicts
    events/<video_id>.json    — list of VideoEvent dicts for that video
"""

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import VIDEO_DB_DIR, VIDEO_INDEX_FILE

logger = logging.getLogger(__name__)

_EVENTS_DIR: Path = VIDEO_DB_DIR / "events"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, data: Any) -> None:
    tmp = path.with_suffix(".tmp.json")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("video_store: failed to read %s — %s", path.name, exc)
    return default


class VideoStore:
    """Manages video index + per-video event files with an RLock."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        VIDEO_DB_DIR.mkdir(parents=True, exist_ok=True)
        _EVENTS_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Video index
    # ------------------------------------------------------------------

    def _load_index(self) -> list[dict]:
        return _read_json(VIDEO_INDEX_FILE, [])

    def _save_index(self, records: list[dict]) -> None:
        _atomic_write(VIDEO_INDEX_FILE, records)

    def add_video(
        self,
        *,
        filename: str,
        file_path: str,
        file_size: int,
        original_name: str,
    ) -> dict:
        """Create a new video record in pending state and return it."""
        video_id = str(uuid.uuid4())[:12]
        record: dict = {
            "id":            video_id,
            "filename":      filename,
            "original_name": original_name,
            "file_path":     file_path,
            "file_size":     file_size,
            "status":        "pending",   # pending | analyzing | done | error
            "progress":      0,
            "error":         None,
            "created_at":    _now_iso(),
            "analyzed_at":   None,
            "duration_secs": None,
            "fps":           None,
            "resolution":    None,
            "frame_count":   None,
            "event_count":   0,
            "thumbnail_path": None,
            "labels":        [],          # top detected object labels
            "summary":       "",
        }
        with self._lock:
            records = self._load_index()
            records.append(record)
            self._save_index(records)
        return record

    def update_video(self, video_id: str, **kwargs: Any) -> dict | None:
        """Patch fields on an existing video record."""
        with self._lock:
            records = self._load_index()
            for rec in records:
                if rec["id"] == video_id:
                    rec.update(kwargs)
                    self._save_index(records)
                    return rec
        return None

    def get_video(self, video_id: str) -> dict | None:
        with self._lock:
            for rec in self._load_index():
                if rec["id"] == video_id:
                    return rec
        return None

    def list_videos(self) -> list[dict]:
        with self._lock:
            return list(reversed(self._load_index()))

    def delete_video(self, video_id: str) -> bool:
        """Remove video record and its event file. Returns True if found."""
        with self._lock:
            records = self._load_index()
            new = [r for r in records if r["id"] != video_id]
            if len(new) == len(records):
                return False
            self._save_index(new)

        events_file = _EVENTS_DIR / f"{video_id}.json"
        events_file.unlink(missing_ok=True)
        return True

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _events_file(self, video_id: str) -> Path:
        return _EVENTS_DIR / f"{video_id}.json"

    def append_events(self, video_id: str, events: list[dict]) -> None:
        """Append a batch of events to the per-video event file."""
        if not events:
            return
        path = self._events_file(video_id)
        with self._lock:
            existing: list[dict] = _read_json(path, [])
            existing.extend(events)
            _atomic_write(path, existing)
            # keep event_count in sync on the index record
            self.update_video(video_id, event_count=len(existing))

    def get_events(
        self,
        video_id: str,
        *,
        event_type: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict]:
        path = self._events_file(video_id)
        with self._lock:
            events: list[dict] = _read_json(path, [])
        if event_type:
            events = [e for e in events if e.get("type") == event_type]
        return events[offset: offset + limit]

    def search_events(self, query: str, limit: int = 50) -> list[dict]:
        """Full-text keyword search across all video events."""
        q = query.lower().strip()
        if not q:
            return []
        results: list[dict] = []
        with self._lock:
            for rec in self._load_index():
                path = self._events_file(rec["id"])
                events: list[dict] = _read_json(path, [])
                for ev in events:
                    haystack = (ev.get("description", "") + " " + ev.get("label", "")).lower()
                    if q in haystack:
                        results.append({**ev, "video_id": rec["id"], "video_name": rec["original_name"]})
                if len(results) >= limit:
                    break
        return results[:limit]


video_store = VideoStore()
