"""
Digital Soul Profiling — passive behavioural analysis of local memory metadata.

Privacy-first: analyses ONLY timestamps, app names, and keyword frequencies.
No personal content is read or transmitted. All computation is local.

Generates:
  top_apps            list[(app, count, pct)]  — most-used apps
  active_hours        dict[int, int]            — hour → memory count heatmap
  peak_period         str                        — human-readable peak hours
  scene_distribution  dict[str, int]             — scene_type → count
  workflow_summary    str                        — dominant workflow description
  memory_span_days    float
  total_memories      int
  insights            list[str]                 — 3–6 plain-English bullets
"""

import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_SECONDS = 60   # profile is re-computed at most once per minute
_cache: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_hour(iso: str) -> int | None:
    try:
        dt = datetime.fromisoformat(iso)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.hour
    except Exception:
        return None


def _span_days(memories: list[dict]) -> float:
    timestamps = []
    for m in memories:
        ts = m.get("created_at", "")
        try:
            dt = datetime.fromisoformat(ts)
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            timestamps.append(dt)
        except Exception:
            continue
    if len(timestamps) < 2:
        return 0.0
    delta = max(timestamps) - min(timestamps)
    return round(delta.total_seconds() / 86_400, 1)


def _peak_period(hour_counts: dict[int, int]) -> str:
    if not hour_counts:
        return "unknown"
    ranked = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
    top_hours = sorted(h for h, _ in ranked[:3])
    if not top_hours:
        return "unknown"
    lo, hi = min(top_hours), max(top_hours)
    def _fmt(h: int) -> str:
        return datetime(2000, 1, 1, h).strftime("%-I %p").lstrip("0") if h else "12 AM"
    # Windows strftime doesn't support %-I; use a manual approach
    def _fmt_h(h: int) -> str:
        suffix = "AM" if h < 12 else "PM"
        hr = h % 12 or 12
        return f"{hr} {suffix}"
    return f"{_fmt_h(lo)}–{_fmt_h(hi)}"


def _extract_keywords_from_memories(memories: list[dict], n: int = 10) -> list[str]:
    from app.services.session_service import NOISE_WORDS
    freq: Counter = Counter()
    for m in memories:
        for text_field in (m.get("title", ""), m.get("text", "")[:400]):
            for word in re.findall(r"[a-zA-Z]{3,}", text_field.lower()):
                if word not in NOISE_WORDS:
                    freq[word] += 1
    return [w for w, _ in freq.most_common(n)]


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def _compute_profile(memories: list[dict]) -> dict[str, Any]:
    total = len(memories)
    if total == 0:
        return _empty_profile()

    # App usage
    app_counts: Counter = Counter()
    for m in memories:
        app = (m.get("metadata") or {}).get("app_name")
        if app:
            app_counts[app] += 1

    top_apps = [
        {"app": app, "count": count, "pct": round(count / total * 100)}
        for app, count in app_counts.most_common(5)
    ]

    # Hourly activity heatmap
    hour_counts: dict[int, int] = defaultdict(int)
    for m in memories:
        h = _parse_hour(m.get("created_at", ""))
        if h is not None:
            hour_counts[h] += 1

    # Scene type distribution (from vision analysis metadata)
    scene_counts: Counter = Counter()
    workflow_counts: Counter = Counter()
    for m in memories:
        meta = m.get("metadata") or {}
        sc = meta.get("scene_type")
        wf = meta.get("workflow_type")
        if sc and sc != "unknown":
            scene_counts[sc] += 1
        if wf and wf != "other":
            workflow_counts[wf] += 1

    # Type distribution
    type_counts: Counter = Counter(m.get("type", "unknown") for m in memories)

    # Memory span
    span = _span_days(memories)
    peak = _peak_period(dict(hour_counts))

    # Dominant workflow
    dominant_workflow = (
        workflow_counts.most_common(1)[0][0] if workflow_counts else "unknown"
    )

    # Top keywords
    top_kws = _extract_keywords_from_memories(memories, n=8)

    # Build human-readable insights
    insights: list[str] = []

    if top_apps:
        app0 = top_apps[0]
        insights.append(f"Most-used app: {app0['app']} ({app0['pct']}% of captures)")

    if hour_counts:
        insights.append(f"Most active during {peak}")

    if dominant_workflow != "unknown":
        insights.append(f"Primary workflow: {dominant_workflow}")

    if span > 0:
        daily_avg = round(total / span) if span > 0 else total
        insights.append(f"{total} memories captured over {span} days (~{daily_avg}/day)")

    if type_counts.get("pdf", 0) > 0:
        insights.append(f"{type_counts['pdf']} PDF document(s) ingested")

    if type_counts.get("voice", 0) > 0:
        insights.append(f"{type_counts['voice']} voice recording(s) transcribed")

    if top_kws:
        kw_str = ", ".join(top_kws[:5])
        insights.append(f"Recurring topics: {kw_str}")

    # Dominant sources
    source_counts: Counter = Counter(m.get("source", "unknown") for m in memories)
    dominant_sources = [
        {"source": src, "count": cnt}
        for src, cnt in source_counts.most_common(5)
    ]

    # Workflow patterns (enumerate non-trivial workflows)
    workflow_patterns: list[str] = []
    if workflow_counts:
        for wf, cnt in workflow_counts.most_common(3):
            workflow_patterns.append(
                f"Your recent activity suggests frequent {wf} sessions ({cnt} captures)."
            )
    if not workflow_patterns:
        workflow_patterns.append("No clear workflow patterns detected yet.")

    # Productivity notes
    productivity_notes: list[str] = []
    if span > 0:
        daily_avg = round(total / span)
        if daily_avg >= 50:
            productivity_notes.append(f"High capture rate: ~{daily_avg} captures/day.")
        elif daily_avg >= 10:
            productivity_notes.append(f"Moderate capture rate: ~{daily_avg} captures/day.")
    if type_counts.get("video", 0) > 0:
        productivity_notes.append(f"{type_counts['video']} video(s) analysed for activity intelligence.")
    if type_counts.get("voice", 0) > 0:
        productivity_notes.append(f"{type_counts['voice']} audio recording(s) in memory.")
    if type_counts.get("pdf", 0) > 0:
        productivity_notes.append(f"{type_counts['pdf']} document(s) indexed for search.")
    if not productivity_notes:
        productivity_notes.append("Keep capturing to see productivity patterns.")

    # Confidence based on data richness
    data_score = min(total / 50.0, 1.0)  # full confidence at 50+ memories
    confidence = round(data_score, 2)

    return {
        "top_apps":            top_apps,
        "active_hours":        dict(hour_counts),
        "peak_period":         peak,
        "scene_distribution":  dict(scene_counts.most_common(6)),
        "workflow_summary":    dominant_workflow,
        "workflow_patterns":   workflow_patterns,
        "dominant_sources":    dominant_sources,
        "productivity_notes":  productivity_notes,
        "type_distribution":   dict(type_counts.most_common()),
        "memory_span_days":    span,
        "total_memories":      total,
        "top_keywords":        top_kws,
        "insights":            insights,
        "confidence":          confidence,
        "privacy_note": (
            "All profiling is local-only. No data leaves your machine. "
            "This profile describes observed workflow patterns only — "
            "no personal identity, health, or behavioural inference is made."
        ),
    }


def _empty_profile() -> dict[str, Any]:
    return {
        "top_apps":            [],
        "active_hours":        {},
        "peak_period":         "unknown",
        "scene_distribution":  {},
        "workflow_summary":    "unknown",
        "workflow_patterns":   ["No workflow patterns detected yet."],
        "dominant_sources":    [],
        "productivity_notes":  ["No memories recorded yet."],
        "type_distribution":   {},
        "memory_span_days":    0.0,
        "total_memories":      0,
        "top_keywords":        [],
        "insights":            ["No memories recorded yet. Start the screen watcher to begin."],
        "confidence":          0.0,
        "privacy_note": (
            "All profiling is local-only. No data leaves your machine. "
            "This profile describes observed workflow patterns only."
        ),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

import time as _time

def get_profile(memories: list[dict]) -> dict[str, Any]:
    """
    Return a behavioural profile for the given memory list.
    Results are cached for _CACHE_SECONDS to avoid recomputing on every request.
    """
    now = _time.monotonic()
    cached_at = _cache.get("_ts", 0)
    cached_count = _cache.get("_count", -1)

    if now - cached_at < _CACHE_SECONDS and cached_count == len(memories):
        return _cache.get("profile", _empty_profile())

    profile = _compute_profile(memories)
    _cache["profile"]  = profile
    _cache["_ts"]      = now
    _cache["_count"]   = len(memories)
    return profile
