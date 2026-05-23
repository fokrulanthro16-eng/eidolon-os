import json
import logging
import threading
from pathlib import Path

from app.core.config import MEMORY_DB_FILE
from app.utils.time import utc_now_iso

logger = logging.getLogger(__name__)

# Required fields every memory item must have
_REQUIRED_FIELDS = ("id", "type", "title", "created_at")


def _is_valid(item: object) -> bool:
    """Return True only for dicts that have the minimum required keys."""
    return isinstance(item, dict) and all(item.get(f) for f in _REQUIRED_FIELDS)


class LocalMemoryStore:
    """
    Thread-safe, atomic JSON-backed memory store.

    Storage layout:
        memories.json           — active database
        memories.tmp.json       — in-flight write buffer (replaced atomically)
        memories.corrupt.*.json — renamed on parse failure, never silently lost

    All writes go through save_all() which:
        1. Acquires the instance-level RLock
        2. Writes to memories.tmp.json
        3. Atomically replaces memories.json via Path.replace()

    The RLock is reentrant so nested calls (e.g. update → save_all) are safe.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Internal I/O
    # ------------------------------------------------------------------

    def load_all(self) -> list[dict]:
        if not MEMORY_DB_FILE.exists():
            return []

        raw = MEMORY_DB_FILE.read_text(encoding="utf-8").strip()
        if not raw:
            return []

        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                raise ValueError("Root element is not a list")
            # Filter out any malformed entries without crashing
            valid = [it for it in data if _is_valid(it)]
            if len(valid) < len(data):
                logger.warning(
                    "Skipped %d malformed item(s) while loading memories.",
                    len(data) - len(valid),
                )
            return valid
        except (json.JSONDecodeError, ValueError) as exc:
            corrupt_path = MEMORY_DB_FILE.with_name(
                f"memories.corrupt.{utc_now_iso().replace(':', '-').replace('+', 'Z')}.json"
            )
            try:
                MEMORY_DB_FILE.rename(corrupt_path)
            except OSError:
                pass
            logger.error(
                "memories.json was corrupted (%s). Renamed to %s. Starting fresh.",
                exc,
                corrupt_path.name,
            )
            return []

    def save_all(self, items: list[dict]) -> None:
        tmp = MEMORY_DB_FILE.with_suffix(".tmp.json")
        try:
            tmp.write_text(
                json.dumps(items, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(MEMORY_DB_FILE)
        except OSError as exc:
            logger.error("Failed to save memories: %s", exc)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # Public API  (all write operations are lock-protected)
    # ------------------------------------------------------------------

    def add(self, item: dict) -> dict:
        if not _is_valid(item):
            raise ValueError(f"Item missing required fields: {item.get('id', '?')!r}")
        with self._lock:
            items = self.load_all()
            items.append(item)
            self.save_all(items)
        return item

    def list(self) -> list[dict]:
        return self.load_all()

    def get(self, memory_id: str) -> dict | None:
        for item in self.load_all():
            if item.get("id") == memory_id:
                return item
        return None

    def delete(self, memory_id: str) -> bool:
        with self._lock:
            items = self.load_all()
            filtered = [i for i in items if i.get("id") != memory_id]
            if len(filtered) == len(items):
                return False
            self.save_all(filtered)
        return True

    def update(self, memory_id: str, patch: dict) -> dict | None:
        with self._lock:
            items = self.load_all()
            for item in items:
                if item.get("id") == memory_id:
                    item.update(patch)
                    item["updated_at"] = utc_now_iso()
                    self.save_all(items)
                    return item
        return None

    def list_raw(self) -> list[dict]:
        """Same as list() — explicit alias for embedding service clarity."""
        return self.load_all()

    def update_embedding(self, memory_id: str, embedding: list[float]) -> None:
        """Persist an embedding vector for a single item (no updated_at touch)."""
        with self._lock:
            items = self.load_all()
            for item in items:
                if item.get("id") == memory_id:
                    item["embedding"] = embedding
                    self.save_all(items)
                    return


# Shared singleton — import this everywhere
memory_store = LocalMemoryStore()
