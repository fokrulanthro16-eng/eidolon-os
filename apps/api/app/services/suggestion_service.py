"""
Autonomous suggestion engine — grounded, explainable, local-only.

All suggestions are backed by actual memory items.
No speculation. No cloud calls. No hallucination.

Suggestion types
----------------
pdf_cluster       — 3+ PDFs share common keywords
workflow_pattern  — common app combination within sessions
time_pattern      — clear peak-activity hours detected
topic_insight     — a topic recurs frequently across memories
session_pattern   — notably long or productive session
app_dominance     — one app accounts for >40% of captures
"""

import hashlib
import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_SECONDS   = 120
_MIN_PDF_CLUSTER = 3      # min PDFs to trigger a cluster suggestion
_APP_DOMINANCE   = 0.40   # threshold for app-dominance suggestion
_LONG_SESSION    = 7200   # seconds (2 h) for long-session detection

_suggestion_cache: list[dict] = []
_cache_ts: float = 0.0
_cache_count: int = -1

# ---------------------------------------------------------------------------
# Dismiss persistence
# ---------------------------------------------------------------------------

def _dismissed_file() -> Path:
    from app.core.config import SESSION_DB_DIR
    SESSION_DB_DIR.mkdir(parents=True, exist_ok=True)
    return SESSION_DB_DIR / "dismissed_suggestions.json"


def _load_dismissed() -> set[str]:
    f = _dismissed_file()
    try:
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            return set(data) if isinstance(data, list) else set()
    except Exception:
        pass
    return set()


def _save_dismissed(ids: set[str]) -> None:
    f = _dismissed_file()
    try:
        tmp = f.with_suffix(".tmp.json")
        tmp.write_text(json.dumps(sorted(ids), indent=2), encoding="utf-8")
        tmp.replace(f)
    except Exception as exc:
        logger.warning("Could not save dismissed suggestions: %s", exc)


def dismiss_suggestion(suggestion_id: str) -> bool:
    """Persist a dismissed suggestion ID. Returns True on success."""
    dismissed = _load_dismissed()
    if suggestion_id in dismissed:
        return True  # already dismissed
    dismissed.add(suggestion_id)
    _save_dismissed(dismissed)
    # Invalidate cache so dismissed suggestion disappears immediately
    global _cache_count
    _cache_count = -1
    return True


def _stable_id(suggestion_type: str, key: str) -> str:
    """Generate a deterministic 12-char ID from type + key."""
    raw = f"{suggestion_type}:{key}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_doc_keywords(text: str, top_n: int = 5) -> list[str]:
    """Return top non-noise keywords from a text chunk."""
    from app.services.session_service import NOISE_WORDS
    freq: Counter = Counter()
    for word in re.findall(r"[a-zA-Z]{4,}", text.lower()):
        if word not in NOISE_WORDS:
            freq[word] += 1
    return [w for w, _ in freq.most_common(top_n)]


def _format_duration(secs: float) -> str:
    if secs < 60:
        return "< 1 min"
    m = int(secs / 60)
    if m < 60:
        return f"{m} min"
    h = int(m / 60)
    rem = m % 60
    return f"{h}h {rem}m" if rem else f"{h}h"


def _peak_window(hour_counts: dict[int, int]) -> str:
    """Return a human-readable peak-hour string."""
    if not hour_counts:
        return ""
    ranked = [h for h, _ in sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]]
    lo, hi = min(ranked), max(ranked)
    def _h(h: int) -> str:
        suffix = "AM" if h < 12 else "PM"
        return f"{h % 12 or 12}{suffix}"
    return f"{_h(lo)}–{_h(hi)}"


def _uid() -> str:
    import uuid
    return str(uuid.uuid4())[:8]


# ---------------------------------------------------------------------------
# Suggestion generators
# ---------------------------------------------------------------------------

def _pdf_cluster_suggestions(memories: list[dict]) -> list[dict]:
    pdfs = [m for m in memories if m.get("type") == "pdf"]
    if len(pdfs) < _MIN_PDF_CLUSTER:
        return []

    # Group PDFs by overlapping keywords
    pdf_kws: list[tuple[dict, list[str]]] = []
    for pdf in pdfs:
        kws = _extract_doc_keywords(pdf.get("text", "") + " " + pdf.get("title", ""))
        pdf_kws.append((pdf, kws))

    # Count keyword co-occurrences
    kw_to_pdfs: dict[str, list[str]] = {}
    for pdf, kws in pdf_kws:
        for kw in kws:
            kw_to_pdfs.setdefault(kw, []).append(pdf["id"])

    suggestions = []
    seen_combos: set[frozenset] = set()

    for kw, ids in sorted(kw_to_pdfs.items(), key=lambda x: len(x[1]), reverse=True):
        if len(ids) < _MIN_PDF_CLUSTER:
            continue
        combo = frozenset(ids[:6])
        if combo in seen_combos:
            continue
        seen_combos.add(combo)

        titles = [m.get("title", m["id"]) for m in memories if m["id"] in ids[:4]]
        title_str = ", ".join(f'"{t}"' for t in titles[:2])
        more = f" (+{len(ids) - 2} more)" if len(ids) > 2 else ""

        suggestions.append({
            "id":         _stable_id("pdf_cluster", kw),
            "type":       "pdf_cluster",
            "title":      f'PDF cluster: {kw}',
            "text":       f'You have {len(ids)} PDFs about "{kw}"',
            "detail":     f"Includes {title_str}{more}. Consider asking PDF Chat for a cross-document summary.",
            "reason":     f"{len(ids)} PDFs share the keyword '{kw}'",
            "confidence": min(0.5 + 0.1 * len(ids), 0.95),
            "memory_ids": ids[:6],
            "action":     f"Search PDFs for: {kw}",
        })
        if len(suggestions) >= 2:
            break

    return suggestions


def _app_dominance_suggestion(memories: list[dict]) -> list[dict]:
    total = len(memories)
    if total < 5:
        return []

    app_counts: Counter = Counter()
    for m in memories:
        app = (m.get("metadata") or {}).get("app_name")
        if app:
            app_counts[app] += 1

    if not app_counts:
        return []

    top_app, top_count = app_counts.most_common(1)[0]
    pct = top_count / total

    if pct < _APP_DOMINANCE:
        return []

    ids = [
        m["id"] for m in memories
        if (m.get("metadata") or {}).get("app_name") == top_app
    ][:6]

    return [{
        "id":         _stable_id("app_dominance", top_app),
        "type":       "app_dominance",
        "title":      f"Dominant app: {top_app}",
        "text":       f"{top_app} appears in {round(pct * 100)}% of your captures",
        "detail":     f"Your workspace is heavily {top_app}-focused. That's {top_count} out of {total} recorded memories.",
        "reason":     f"{top_app} accounts for {round(pct*100)}% of all captures",
        "confidence": 0.90,
        "memory_ids": ids,
        "action":     f"Search for: {top_app}",
    }]


def _time_pattern_suggestion(memories: list[dict]) -> list[dict]:
    from collections import defaultdict
    hour_counts: dict[int, int] = defaultdict(int)
    for m in memories:
        try:
            ts = m.get("created_at", "")
            dt = datetime.fromisoformat(ts)
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            hour_counts[dt.hour] += 1
        except Exception:
            continue

    if not hour_counts:
        return []

    total_hours_with_data = len(hour_counts)
    if total_hours_with_data < 3:
        return []

    ranked = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
    top3_hours = {h for h, _ in ranked[:3]}
    top3_count = sum(c for h, c in ranked[:3])
    pct = top3_count / sum(hour_counts.values())

    if pct < 0.45:
        return []

    peak = _peak_window(dict(hour_counts))
    return [{
        "id":         _stable_id("time_pattern", peak),
        "type":       "time_pattern",
        "title":      f"Peak hours: {peak}",
        "text":       f"You're most active between {peak}",
        "detail":     f"{round(pct * 100)}% of your captures fall in this window. EIDOLON is learning your rhythm.",
        "reason":     f"{round(pct*100)}% of activity in {peak} window",
        "confidence": round(pct, 2),
        "memory_ids": [],
        "action":     None,
    }]


def _topic_insight_suggestion(memories: list[dict]) -> list[dict]:
    recent = memories[-60:] if len(memories) > 60 else memories
    kw_to_ids: dict[str, list[str]] = {}
    for m in recent:
        text = m.get("title", "") + " " + m.get("text", "")[:600]
        for kw in _extract_doc_keywords(text, top_n=4):
            kw_to_ids.setdefault(kw, []).append(m["id"])

    if not kw_to_ids:
        return []

    top_kw, ids = max(kw_to_ids.items(), key=lambda x: len(x[1]))
    if len(ids) < 4:
        return []

    return [{
        "id":         _stable_id("topic_insight", top_kw),
        "type":       "topic_insight",
        "title":      f'Recurring topic: {top_kw}',
        "text":       f'"{top_kw}" keeps appearing in your recent work',
        "detail":     f"Found in {len(ids)} recent memories. This may be an evolving project or research thread.",
        "reason":     f"Keyword '{top_kw}' found in {len(ids)} memories",
        "confidence": min(0.4 + 0.05 * len(ids), 0.85),
        "memory_ids": ids[:6],
        "action":     f"Search memories for: {top_kw}",
    }]


def _session_pattern_suggestion(memories: list[dict]) -> list[dict]:
    """Surface the most notable (long or dense) session."""
    try:
        from app.services.session_service import detect_sessions
        sessions = detect_sessions(memories)
        if not sessions:
            return []

        long = [s for s in sessions if s.get("duration_secs", 0) >= _LONG_SESSION]
        if not long:
            return []

        best = max(long, key=lambda s: s.get("duration_secs", 0))
        dur  = _format_duration(best["duration_secs"])
        title = best.get("title", "a session")
        ids  = [m["id"] for m in memories if m.get("session_id") == best.get("session_id")][:6]

        sid = best.get("session_id", "")
        return [{
            "id":         _stable_id("session_pattern", sid or title),
            "type":       "session_pattern",
            "title":      f"Deep work: {dur}",
            "text":       f'You had a {dur} deep-work session: "{title}"',
            "detail":     f"{best.get('memory_count', 0)} captures in one continuous block. That's real focus.",
            "reason":     f"Session lasted {dur} with {best.get('memory_count', 0)} captures",
            "confidence": 0.85,
            "memory_ids": ids,
            "action":     f"View session: {sid}",
        }]
    except Exception as exc:
        logger.debug("Session pattern suggestion failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

import time as _time


def get_suggestions(memories: list[dict]) -> list[dict]:
    """
    Return a ranked list of up to 5 suggestions grounded in memory data.
    Cached for _CACHE_SECONDS. Dismissed suggestions are filtered out.
    """
    global _suggestion_cache, _cache_ts, _cache_count

    now = _time.monotonic()
    if now - _cache_ts < _CACHE_SECONDS and _cache_count == len(memories):
        dismissed = _load_dismissed()
        return [s for s in _suggestion_cache if s["id"] not in dismissed]

    suggestions: list[dict] = []
    try:
        suggestions += _pdf_cluster_suggestions(memories)
        suggestions += _app_dominance_suggestion(memories)
        suggestions += _time_pattern_suggestion(memories)
        suggestions += _topic_insight_suggestion(memories)
        suggestions += _session_pattern_suggestion(memories)
    except Exception as exc:
        logger.warning("Suggestion generation failed: %s", exc)

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    for s in suggestions:
        s.setdefault("created_at", ts)
        s.setdefault("dismissed", False)
        s.setdefault("source_memory_ids", s.get("memory_ids", []))

    # Sort by confidence descending, cap at 5
    suggestions.sort(key=lambda s: s["confidence"], reverse=True)
    suggestions = suggestions[:5]

    _suggestion_cache = suggestions
    _cache_ts         = now
    _cache_count      = len(memories)

    dismissed = _load_dismissed()
    return [s for s in suggestions if s["id"] not in dismissed]
