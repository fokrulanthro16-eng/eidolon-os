"""
In-memory chat session store.

Sessions hold conversation history so the LLM can reference prior turns.
Automatically evicts oldest sessions when the cap is reached.
All state is lost on server restart — by design (local-first, no DB needed).
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.utils.time import utc_now_iso

_MAX_SESSIONS   = 50
_MAX_MESSAGES   = 20   # per session
_TTL_HOURS      = 24


def _parse_utc(iso: str) -> datetime:
    try:
        t = datetime.fromisoformat(iso)
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


@dataclass
class _Msg:
    role: str       # "user" | "assistant"
    content: str
    timestamp: str = field(default_factory=utc_now_iso)


@dataclass
class _Session:
    session_id: str     = field(default_factory=lambda: uuid.uuid4().hex[:8])
    messages:   list    = field(default_factory=list)
    created_at: str     = field(default_factory=utc_now_iso)
    last_activity: str  = field(default_factory=utc_now_iso)


class ChatSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_or_create(self, session_id: str | None = None) -> _Session:
        """Return existing session or create a new one."""
        if session_id and session_id in self._sessions:
            s = self._sessions[session_id]
            s.last_activity = utc_now_iso()
            return s
        self._evict_if_needed()
        s = _Session()
        self._sessions[s.session_id] = s
        return s

    def add_message(self, session_id: str, role: str, content: str) -> None:
        if session_id not in self._sessions:
            return
        s = self._sessions[session_id]
        s.messages.append(_Msg(role=role, content=content))
        if len(s.messages) > _MAX_MESSAGES:
            s.messages = s.messages[-_MAX_MESSAGES:]
        s.last_activity = utc_now_iso()

    def get_history(self, session_id: str, n: int = 6) -> list[dict]:
        """Last n turns as [{"role": ..., "content": ...}]."""
        if session_id not in self._sessions:
            return []
        return [
            {"role": m.role, "content": m.content}
            for m in self._sessions[session_id].messages[-n:]
        ]

    def list_sessions(self) -> list[dict]:
        return [
            {
                "session_id":     s.session_id,
                "message_count":  len(s.messages),
                "created_at":     s.created_at,
                "last_activity":  s.last_activity,
                "preview":        next(
                    (m.content[:80] for m in s.messages if m.role == "user"), ""
                ),
            }
            for s in self._sessions.values()
        ]

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evict_if_needed(self) -> None:
        if len(self._sessions) < _MAX_SESSIONS:
            return
        now = datetime.now(timezone.utc)
        expired = [
            sid for sid, s in self._sessions.items()
            if (now - _parse_utc(s.last_activity)).total_seconds() > _TTL_HOURS * 3600
        ]
        for sid in expired:
            del self._sessions[sid]
        # Still over cap — evict the single oldest session
        if len(self._sessions) >= _MAX_SESSIONS:
            oldest = min(self._sessions.items(), key=lambda kv: kv[1].last_activity)
            del self._sessions[oldest[0]]


# Shared singleton
chat_session_store = ChatSessionStore()
