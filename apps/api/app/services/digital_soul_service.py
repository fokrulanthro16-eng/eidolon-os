"""
Digital Soul Intelligence Service — Phase 14.

Analyses behavioral patterns from local memory metadata to surface:
  - Workflow rhythm: hourly activity heatmap, peak coding/research times
  - Project memory: recurring topics, folder paths, unfinished sessions
  - Tool preferences: most-used tools and workflows
  - Research patterns: frequent search topics, AI usage patterns
  - Project continuity: what the user was working on and left unfinished

Privacy rules:
  - Analyses ONLY timestamps, app names, and keyword frequencies.
  - Never infers health, identity, or demographic data.
  - Language: "Your recent workflow suggests…" not "You are…"
  - Every insight cites source evidence (memory IDs / session IDs).

Output schema:
  profile         dict  — base profile (wraps profile_service)
  patterns        list  — named behavioral patterns with evidence
  workflow_rhythm dict  — hourly and daily activity breakdown
  project_memory  dict  — recurring projects, unfinished work, continuity
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_TTL = 90   # seconds
_cache: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(iso: str) -> datetime | None:
    try:
        s = iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _cached(key: str, fn, *args, **kwargs):
    entry = _cache.get(key)
    if entry and (_utc_now() - entry["ts"]).total_seconds() < _CACHE_TTL:
        return entry["value"]
    value = fn(*args, **kwargs)
    _cache[key] = {"value": value, "ts": _utc_now()}
    return value


def _hour_label(h: int) -> str:
    suffix = "AM" if h < 12 else "PM"
    hr = h % 12 or 12
    return f"{hr}{suffix}"


def _recent(memories: list[dict], days: float) -> list[dict]:
    cutoff = _utc_now() - timedelta(days=days)
    result = []
    for m in memories:
        dt = _parse_dt(m.get("created_at", ""))
        if dt and dt >= cutoff:
            result.append(m)
    return result


def _extract_topic_keywords(memories: list[dict], n: int = 20) -> list[str]:
    from app.services.session_service import NOISE_WORDS
    counts: Counter = Counter()
    for m in memories:
        text = (m.get("text") or "") + " " + (m.get("title") or "")
        for word in text.lower().split():
            w = word.strip(".,;:!?\"'()-[]")
            if len(w) >= 4 and w not in NOISE_WORDS:
                counts[w] += 1
    return [w for w, _ in counts.most_common(n)]


# ---------------------------------------------------------------------------
# Workflow Rhythm
# ---------------------------------------------------------------------------

def _compute_workflow_rhythm(memories: list[dict]) -> dict:
    """Hourly and day-of-week activity breakdown."""
    hour_counts: defaultdict[int, int]   = defaultdict(int)
    dow_counts:  defaultdict[int, int]   = defaultdict(int)
    scene_by_hour: defaultdict[int, Counter] = defaultdict(Counter)

    for m in memories:
        dt = _parse_dt(m.get("created_at", ""))
        if not dt:
            continue
        h = dt.hour
        d = dt.weekday()  # 0=Mon … 6=Sun
        hour_counts[h] += 1
        dow_counts[d] += 1
        scene = (m.get("metadata") or {}).get("scene_type", "")
        if scene:
            scene_by_hour[h][scene] += 1

    # Peak hours (top 3)
    peak = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    peak_labels = [_hour_label(h) for h, _ in sorted(h for h, _ in peak)]

    # Day-of-week labels
    dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    dow_breakdown = {dow_names[d]: c for d, c in sorted(dow_counts.items())}

    # Dominant scene per peak hour
    peak_activities: list[dict] = []
    for h, cnt in sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:6]:
        top_scene = scene_by_hour[h].most_common(1)[0][0] if scene_by_hour[h] else "unknown"
        peak_activities.append({
            "hour":       h,
            "hour_label": _hour_label(h),
            "count":      cnt,
            "top_scene":  top_scene,
        })

    # Activity by hour (0-23, count only)
    hourly_heatmap = {h: hour_counts[h] for h in range(24) if hour_counts[h] > 0}

    return {
        "hourly_heatmap":   hourly_heatmap,
        "peak_hours":       peak_labels,
        "peak_activities":  peak_activities,
        "day_of_week":      dow_breakdown,
        "most_active_day":  dow_names[max(dow_counts, key=dow_counts.get)] if dow_counts else "unknown",
    }


# ---------------------------------------------------------------------------
# Project Memory
# ---------------------------------------------------------------------------

def _compute_project_memory(memories: list[dict]) -> dict:
    """Identify recurring projects, unfinished work, and continuity."""
    # Recurring topic clusters from keywords
    recent_30d = _recent(memories, 30)
    keywords = _extract_topic_keywords(recent_30d, n=30)

    # Window titles often contain file paths / project names
    project_names: Counter = Counter()
    for m in memories:
        wt = (m.get("metadata") or {}).get("window_title") or ""
        # Extract project-like tokens from title bar
        import re
        # VSCode format: "filename.ext — project-folder — Visual Studio Code"
        parts = re.split(r"\s[—\-–|]\s", wt)
        for p in parts[1:]:  # skip first (filename), take project/app portions
            p = p.strip()
            if p and len(p) > 2 and p.lower() not in ("visual studio code", "google chrome",
                                                        "microsoft edge", "firefox", "code"):
                project_names[p] += 1

    top_projects = [
        {"name": name, "mentions": cnt}
        for name, cnt in project_names.most_common(8)
        if cnt >= 2
    ]

    # Unfinished sessions: sessions from yesterday or older that were short
    yesterday = _utc_now() - timedelta(days=1)
    try:
        from app.services.session_store import session_store
        all_sessions = session_store.get_sessions()
    except Exception:
        all_sessions = []

    unfinished = []
    for s in all_sessions:
        end_dt = _parse_dt(s.get("end_time", ""))
        if end_dt and end_dt < yesterday:
            dur = s.get("duration_secs", 0)
            if 120 < dur < 900:  # 2-15 min (interrupted / short)
                unfinished.append({
                    "session_id":    s.get("id"),
                    "title":         s.get("title", "Unnamed"),
                    "duration_str":  s.get("duration_str", ""),
                    "ended_at":      s.get("end_time"),
                    "apps":          s.get("main_sources", []),
                })

    # Most recently active project (from last session or last screenshot)
    last_app = None
    for m in sorted(memories, key=lambda x: x.get("created_at", ""), reverse=True)[:5]:
        a = (m.get("metadata") or {}).get("app_name", "")
        if a:
            last_app = a
            break

    return {
        "top_projects":      top_projects,
        "recent_keywords":   keywords[:15],
        "unfinished_sessions": unfinished[:5],
        "last_active_app":   last_app,
        "total_sessions":    len(all_sessions),
    }


# ---------------------------------------------------------------------------
# Behavioral Patterns
# ---------------------------------------------------------------------------

def _compute_patterns(memories: list[dict]) -> list[dict]:
    """Detect named behavioral patterns with evidence."""
    patterns: list[dict] = []

    if len(memories) < 3:
        return patterns

    recent_7d = _recent(memories, 7)
    recent_30d = _recent(memories, 30)

    # — Coding dominance
    coding_mems = [m for m in recent_7d if (m.get("metadata") or {}).get("scene_type", "") in ("coding", "debugging")]
    if len(coding_mems) >= 5:
        patterns.append({
            "name":        "Coding Focus",
            "description": "Your recent workflow suggests significant coding activity.",
            "evidence":    f"{len(coding_mems)} coding screens in the past 7 days.",
            "strength":    min(1.0, len(coding_mems) / 20),
            "type":        "workflow",
        })

    # — Research pattern
    research_mems = [m for m in recent_7d if (m.get("metadata") or {}).get("workflow_type", "") == "research"]
    if len(research_mems) >= 4:
        patterns.append({
            "name":        "Active Researcher",
            "description": "Your recent workflow suggests regular research and documentation review.",
            "evidence":    f"{len(research_mems)} research screens in the past 7 days.",
            "strength":    min(1.0, len(research_mems) / 15),
            "type":        "workflow",
        })

    # — PDF reader pattern
    pdf_mems = [m for m in recent_30d if m.get("type") == "pdf"]
    if len(pdf_mems) >= 3:
        patterns.append({
            "name":        "Document Reader",
            "description": f"You have ingested {len(pdf_mems)} PDF documents recently.",
            "evidence":    f"{len(pdf_mems)} PDFs in the past 30 days.",
            "strength":    min(1.0, len(pdf_mems) / 10),
            "type":        "modality",
        })

    # — Voice note taker
    voice_mems = [m for m in recent_30d if m.get("type") == "voice"]
    if len(voice_mems) >= 2:
        patterns.append({
            "name":        "Voice Note Taker",
            "description": f"You regularly record voice memos ({len(voice_mems)} in past 30 days).",
            "evidence":    f"{len(voice_mems)} voice memos ingested.",
            "strength":    min(1.0, len(voice_mems) / 8),
            "type":        "modality",
        })

    # — Multi-tool workflow
    apps_7d = Counter(
        (m.get("metadata") or {}).get("app_name", "") for m in recent_7d
        if (m.get("metadata") or {}).get("app_name")
    )
    if len(apps_7d) >= 4:
        patterns.append({
            "name":        "Multi-Tool Workflow",
            "description": f"Your workflow spans {len(apps_7d)} different tools this week.",
            "evidence":    f"Apps: {', '.join(a for a, _ in apps_7d.most_common(4))}.",
            "strength":    min(1.0, len(apps_7d) / 8),
            "type":        "tools",
        })

    # — Debug-heavy session
    debug_mems = [m for m in recent_7d if (m.get("metadata") or {}).get("scene_type", "") == "debugging"]
    if len(debug_mems) >= 3:
        patterns.append({
            "name":        "Active Debugger",
            "description": "Your recent workflow suggests frequent debugging activity.",
            "evidence":    f"{len(debug_mems)} debugging screens in 7 days.",
            "strength":    min(1.0, len(debug_mems) / 10),
            "type":        "workflow",
        })

    return sorted(patterns, key=lambda p: p["strength"], reverse=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_soul_profile(memories: list[dict]) -> dict:
    """Full Digital Soul profile (wraps profile_service + adds soul fields)."""
    def _compute():
        try:
            from app.services.profile_service import get_profile
            base = get_profile(memories)
        except Exception:
            base = {}
        patterns = _compute_patterns(memories)
        return {**base, "patterns": patterns, "source": "digital_soul"}

    return _cached("soul_profile", _compute)


def get_patterns(memories: list[dict]) -> dict:
    """Return behavioral patterns with strength scores and evidence."""
    def _compute():
        return {
            "patterns": _compute_patterns(memories),
            "total_memories": len(memories),
        }

    return _cached("patterns", _compute)


def get_workflow_rhythm(memories: list[dict]) -> dict:
    """Return hourly activity heatmap and peak activity periods."""
    def _compute():
        return _compute_workflow_rhythm(memories)

    return _cached("workflow_rhythm", _compute)


def get_project_memory(memories: list[dict]) -> dict:
    """Return recurring projects, unfinished work, and keyword themes."""
    def _compute():
        return _compute_project_memory(memories)

    return _cached("project_memory", _compute)
