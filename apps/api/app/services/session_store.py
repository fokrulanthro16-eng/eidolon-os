"""
Persistent session cache.

Sessions are computed dynamically from memory timestamps, but recomputing
on every request is wasteful.  This store saves the last computed result to
storage/session-db/sessions.json and returns it if still valid.

Cache validity: memory_count AND gap_minutes must match.  When either
changes (new captures, setting tweak), the store transparently recomputes.

Layout:
    sessions.json        — active cache
    sessions.tmp.json    — in-flight write (replaced atomically)
"""

import json
import logging
import threading

from app.core.config import SESSION_DB_FILE
from app.utils.time import utc_now_iso

logger = logging.getLogger(__name__)


class SessionStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Internal I/O
    # ------------------------------------------------------------------

    def _load(self) -> dict | None:
        if not SESSION_DB_FILE.exists():
            return None
        try:
            raw = SESSION_DB_FILE.read_text(encoding="utf-8").strip()
            if not raw:
                return None
            data = json.loads(raw)
            if not isinstance(data, dict):
                return None
            return data
        except Exception as exc:
            logger.warning("Session cache unreadable (%s) — will recompute.", exc)
            return None

    def _save(self, sessions: list[dict], memory_count: int, gap_minutes: int) -> None:
        tmp = SESSION_DB_FILE.with_suffix(".tmp.json")
        payload = {
            "saved_at":     utc_now_iso(),
            "memory_count": memory_count,
            "gap_minutes":  gap_minutes,
            "count":        len(sessions),
            "sessions":     sessions,
        }
        try:
            tmp.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(SESSION_DB_FILE)
        except OSError as exc:
            logger.error("Failed to persist session cache: %s", exc)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_stale(self, memory_count: int, gap_minutes: int) -> bool:
        """Return True when the cache must be refreshed."""
        data = self._load()
        if data is None:
            return True
        return (
            data.get("memory_count") != memory_count
            or data.get("gap_minutes") != gap_minutes
        )

    def get_sessions(self) -> list[dict]:
        """Return cached sessions (slim — no memories list)."""
        data = self._load()
        return data.get("sessions", []) if data else []

    def get_session_by_id(self, session_id: str) -> dict | None:
        """Look up a slim session from the cache by ID."""
        for s in self.get_sessions():
            if s.get("session_id") == session_id:
                return s
        return None

    def update(self, sessions: list[dict], memory_count: int, gap_minutes: int) -> None:
        """Persist a freshly computed set of slim sessions."""
        with self._lock:
            self._save(sessions, memory_count, gap_minutes)

    def get_or_refresh(
        self,
        items: list[dict],
        gap_minutes: int,
        force: bool = False,
    ) -> list[dict]:
        """
        Return cached sessions if still valid, otherwise recompute, save, and return.
        `items` is the full list of memory dicts from memory_store.
        Returns slim sessions (no 'memories' key).
        """
        memory_count = len(items)
        if not force and not self.is_stale(memory_count, gap_minutes):
            cached = self.get_sessions()
            if cached:
                logger.debug("Session cache hit (%d sessions)", len(cached))
                return cached

        # Recompute
        from app.services.session_service import detect_sessions
        full_sessions = detect_sessions(items, gap_minutes=gap_minutes)
        slim = [{k: v for k, v in s.items() if k != "memories"} for s in full_sessions]
        self.update(slim, memory_count=memory_count, gap_minutes=gap_minutes)
        logger.debug("Session cache refreshed (%d sessions)", len(slim))
        return slim


# Shared singleton — import this everywhere
session_store = SessionStore()
