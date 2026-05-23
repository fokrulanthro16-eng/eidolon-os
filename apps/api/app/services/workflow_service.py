"""
Workflow Service — Phase 11 workflow aggregation from memory items.

Groups screenshot memories into coherent workflow periods and provides:
  - current_workflow()      dict describing what the user is doing right now
  - workflow_timeline(h)    list of workflow periods over last N hours
  - daily_summary(h)        text + stats summary of work done

Grouping rule: consecutive screenshot memories with the same workflow_type
and < GAP_MINUTES between them belong to the same workflow period.

Fallback: when no screenshot memories exist in the requested window,
the service automatically extends the lookback (up to 7 days) and uses
all memory types to estimate activity.
"""

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

GAP_MINUTES   = 5    # gap larger than this = new workflow period
MIN_MEMORIES  = 2    # minimum memories to constitute a workflow period
MAX_HOURS     = 168  # cap for timeline lookback (7 days)

# Fallback lookback ladder when the requested window is empty
_FALLBACK_WINDOWS = [48.0, 72.0, 168.0]   # hours: 2d, 3d, 7d


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dt(iso: str) -> datetime | None:
    """Parse ISO 8601 timestamp. Naive timestamps are assumed UTC."""
    try:
        s = iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            # Treat naive timestamps as UTC (defensive fallback)
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _screenshot_memories(memories: list[dict], since: datetime) -> list[dict]:
    """Filter to screenshot/image memories newer than since, sorted oldest-first."""
    result = []
    for m in memories:
        if m.get("type") not in ("screenshot", "image"):
            continue
        dt = _parse_dt(m.get("created_at", ""))
        if dt and dt >= since:
            result.append({**m, "_dt": dt})
    return sorted(result, key=lambda x: x["_dt"])


def _all_memories_in_window(memories: list[dict], since: datetime) -> list[dict]:
    """Return ALL memory types within the time window, sorted oldest-first."""
    result = []
    for m in memories:
        dt = _parse_dt(m.get("created_at", ""))
        if dt and dt >= since:
            result.append({**m, "_dt": dt})
    return sorted(result, key=lambda x: x["_dt"])


def _workflow_label(wf: str, scene: str, tools: list[str]) -> str:
    """Human-readable workflow label."""
    task_labels = {
        "development":   "Development",
        "research":      "Research",
        "communication": "Communication",
        "creative":      "Creative Work",
        "learning":      "Learning",
        "security":      "Security Review",
        "other":         "General Work",
    }
    base = task_labels.get(wf, "Work")
    if "FastAPI" in tools or "uvicorn" in tools:
        return "Backend Development"
    if "React" in tools or "Next.js" in tools or "TypeScript" in tools:
        return "Frontend Development"
    if scene == "debugging":
        return "Debugging"
    if scene == "api-testing":
        return "API Testing"
    if scene == "ai-chat":
        return "AI Research"
    if scene == "terminal-work":
        return "Terminal / DevOps"
    if scene == "surveillance-review":
        return "Surveillance Review"
    return base


def _group_into_periods(memories: list[dict]) -> list[dict]:
    """Group sorted screenshot memories into workflow periods."""
    if not memories:
        return []

    periods: list[dict] = []
    group: list[dict] = [memories[0]]

    for mem in memories[1:]:
        gap = (mem["_dt"] - group[-1]["_dt"]).total_seconds() / 60
        same_workflow = (
            mem.get("metadata", {}).get("workflow_type", "other")
            == group[-1].get("metadata", {}).get("workflow_type", "other")
        )
        if gap <= GAP_MINUTES and same_workflow:
            group.append(mem)
        else:
            if len(group) >= MIN_MEMORIES:
                periods.append(_summarise_group(group))
            group = [mem]

    if len(group) >= MIN_MEMORIES:
        periods.append(_summarise_group(group))

    return periods


def _summarise_group(group: list[dict]) -> dict:
    """Summarise a group of screenshot memories into a workflow period."""
    start_dt = group[0]["_dt"]
    end_dt   = group[-1]["_dt"]
    duration_mins = round((end_dt - start_dt).total_seconds() / 60, 1)

    apps = [m.get("metadata", {}).get("app_name") or m.get("metadata", {}).get("dominant_app", "")
            for m in group if m.get("metadata")]
    apps = [a for a in apps if a]
    top_app = Counter(apps).most_common(1)[0][0] if apps else "unknown"

    workflow_types = [m.get("metadata", {}).get("workflow_type", "other") for m in group]
    dominant_wf = Counter(workflow_types).most_common(1)[0][0]

    scenes = [m.get("metadata", {}).get("scene_type", "unknown") for m in group]
    dominant_scene = Counter(scenes).most_common(1)[0][0]

    tools: list[str] = []
    tasks: list[str] = []
    for m in group:
        meta = m.get("metadata", {})
        for t in meta.get("active_tools", []):
            if t not in tools:
                tools.append(t)
        pt = meta.get("probable_task", "")
        if pt and pt not in tasks:
            tasks.append(pt)

    label = _workflow_label(dominant_wf, dominant_scene, tools)

    return {
        "start":          start_dt.isoformat(),
        "end":            end_dt.isoformat(),
        "duration_mins":  duration_mins,
        "memory_count":   len(group),
        "dominant_app":   top_app,
        "workflow_type":  dominant_wf,
        "scene_type":     dominant_scene,
        "label":          label,
        "active_tools":   tools[:6],
        "sample_tasks":   tasks[:3],
    }


def _sessions_in_window(since: datetime) -> int:
    """Count sessions that overlap with the time window."""
    try:
        from app.services.session_store import session_store
        sessions = session_store.get_sessions()
        count = 0
        for s in sessions:
            ts = s.get("end_time") or s.get("start_time") or ""
            dt = _parse_dt(ts)
            if dt and dt >= since:
                count += 1
        return count
    except Exception:
        return 0


def _summary_from_all_types(memories: list[dict], since: datetime, window_hours: float) -> dict:
    """
    Build a daily summary when no screenshot memories are available.
    Uses all memory types to estimate activity.
    """
    all_recent = _all_memories_in_window(memories, since)
    total_mems = len(memories)

    if not all_recent:
        return {
            "total_memories":   total_mems,
            "screenshot_count": 0,
            "active_hours":     0,
            "workflow_breakdown": {},
            "top_apps":         [],
            "top_tools":        [],
            "key_activities":   [],
            "workflow_periods":  0,
            "summary_text":     "No activity recorded in the last 24 hours. Start the screen watcher to capture activity automatically.",
        }

    # Estimate active time from timestamp span
    span_secs = (all_recent[-1]["_dt"] - all_recent[0]["_dt"]).total_seconds()
    active_hours = round(span_secs / 3600, 1)

    # App distribution from metadata
    all_apps: Counter = Counter()
    for m in all_recent:
        app = (m.get("metadata") or {}).get("app_name") or (m.get("metadata") or {}).get("dominant_app") or ""
        if app:
            all_apps[app] += 1

    # Type breakdown
    type_counts = Counter(m.get("type", "memory") for m in all_recent)

    # Sessions as proxy for workflow periods
    n_periods = _sessions_in_window(since) or max(1, len(all_recent) // 8)

    # Build summary text
    window_label = "24h" if window_hours <= 24 else f"{int(window_hours / 24)}d"
    parts: list[str] = []
    if active_hours > 0:
        parts.append(f"Active for ~{active_hours}h.")
    type_parts = [f"{c} {t}{'s' if c != 1 else ''}" for t, c in type_counts.most_common(3)]
    if type_parts:
        parts.append(f"Memories: {', '.join(type_parts)}.")
    if all_apps:
        parts.append(f"Mostly in {all_apps.most_common(1)[0][0]}.")
    if not parts:
        parts.append(f"{len(all_recent)} memories in the last {window_label}.")
    summary_text = " ".join(parts)

    return {
        "total_memories":    total_mems,
        "screenshot_count":  0,
        "active_hours":      active_hours,
        "workflow_breakdown": {},
        "top_apps":          [{"app": a, "count": c} for a, c in all_apps.most_common(5)],
        "top_tools":         [],
        "key_activities":    [],
        "workflow_periods":  n_periods,
        "summary_text":      summary_text,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_workflow_timeline(memories: list[dict], hours: float = 24.0) -> list[dict]:
    """
    Return a list of workflow periods for the last `hours` hours,
    newest first. Extends lookback if the requested window is empty.
    """
    hours = min(hours, MAX_HOURS)
    since = _utc_now() - timedelta(hours=hours)
    shots = _screenshot_memories(memories, since)

    # Extend lookback if nothing found in the initial window
    if not shots:
        for fallback in _FALLBACK_WINDOWS:
            since = _utc_now() - timedelta(hours=fallback)
            shots = _screenshot_memories(memories, since)
            if shots:
                break

    periods = _group_into_periods(shots)
    return list(reversed(periods))


def get_current_workflow(memories: list[dict]) -> dict:
    """
    Return the active workflow period if one is ongoing (last 10 minutes),
    otherwise return a short 'idle' dict.
    """
    since = _utc_now() - timedelta(minutes=10)
    recent = _screenshot_memories(memories, since)

    if not recent:
        return {
            "active": False,
            "label": "Idle",
            "dominant_app": None,
            "workflow_type": "other",
            "duration_mins": 0,
            "active_tools": [],
            "probable_task": None,
        }

    period = _summarise_group(recent)
    period["active"] = True
    return period


def get_daily_summary(memories: list[dict], hours: float = 24.0) -> dict:
    """
    Return a structured daily summary dict.

    When no screenshot memories exist in the requested window, automatically
    extends the lookback (up to 7 days) and falls back to all memory types
    so the summary always reflects actual recorded activity.
    """
    hours = min(hours, MAX_HOURS)
    since = _utc_now() - timedelta(hours=hours)
    shots = _screenshot_memories(memories, since)
    actual_window = hours

    # Extend lookback if no screenshots in requested window
    if not shots:
        for fallback in _FALLBACK_WINDOWS:
            since = _utc_now() - timedelta(hours=fallback)
            shots = _screenshot_memories(memories, since)
            if shots:
                actual_window = fallback
                break

    # No screenshots even after extending — use all memory types as fallback
    if not shots:
        # Reset to original window but pull all types
        since = _utc_now() - timedelta(hours=hours)
        all_recent = _all_memories_in_window(memories, since)
        if not all_recent:
            # Try wider window for non-screenshot memories
            for fallback in _FALLBACK_WINDOWS:
                since = _utc_now() - timedelta(hours=fallback)
                all_recent = _all_memories_in_window(memories, since)
                if all_recent:
                    actual_window = fallback
                    break
        return _summary_from_all_types(memories, since, actual_window)

    # ── Normal path: screenshots exist ──
    periods = _group_into_periods(shots)

    total_mems = len(memories)
    screenshot_count = len(shots)

    workflow_mins: Counter = Counter()
    all_apps: Counter = Counter()
    all_tools: Counter = Counter()
    key_activities: list[str] = []

    for p in periods:
        workflow_mins[p["label"]] += p["duration_mins"]
        all_apps[p["dominant_app"]] += 1
        for t in p["active_tools"]:
            all_tools[t] += 1
        for task in p["sample_tasks"]:
            if task not in key_activities:
                key_activities.append(task)

    active_mins = sum(workflow_mins.values())
    active_hours = round(active_mins / 60, 1)

    # If screenshots exist but no workflow periods (all single-capture sessions),
    # fall back to timestamp span as active hours estimate
    if active_hours == 0 and shots:
        span_secs = (shots[-1]["_dt"] - shots[0]["_dt"]).total_seconds()
        active_hours = round(span_secs / 3600, 1)
        # Collect apps from the shots directly
        for shot in shots:
            app = (shot.get("metadata") or {}).get("app_name", "")
            if app:
                all_apps[app] += 1

    top_apps  = all_apps.most_common(5)
    top_tools = all_tools.most_common(6)

    window_label = "24h" if actual_window <= 24 else f"{int(actual_window / 24)}d"
    parts: list[str] = [f"Active for ~{active_hours}h in the last {window_label}."]
    if top_apps:
        parts.append(f"Mostly in {top_apps[0][0]}.")
    if workflow_mins:
        top_wf = max(workflow_mins, key=workflow_mins.__getitem__)
        parts.append(f"Primarily: {top_wf}.")
    if top_tools:
        parts.append(f"Tools: {', '.join(t for t, _ in top_tools[:3])}.")
    summary_text = " ".join(parts)

    return {
        "total_memories":     total_mems,
        "screenshot_count":   screenshot_count,
        "active_hours":       active_hours,
        "workflow_breakdown": dict(workflow_mins),
        "top_apps":           [{"app": a, "count": c} for a, c in top_apps],
        "top_tools":          [{"tool": t, "count": c} for t, c in top_tools],
        "key_activities":     key_activities[:6],
        "workflow_periods":   len(periods) or _sessions_in_window(since),
        "summary_text":       summary_text,
    }
