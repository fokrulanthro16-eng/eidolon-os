"""
Intelligence Service — Phase 21.

Cognitive profile synthesis, timeline trend analysis, memory clustering,
and proactive insight generation. Builds on the existing profile_service
and workflow_service without replacing them.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain taxonomy — used across clustering, scoring, and insight generation
# ---------------------------------------------------------------------------

DOMAINS: dict[str, list[str]] = {
    "Camera & Vision":      [
        "camera", "detection", "person", "object", "vision",
        "cctv", "stationary", "live_camera", "frame", "yolo",
        "prediction", "tracking", "bounding", "monitor", "surveillance",
    ],
    "AI & ML":              [
        "ai", "model", "gemini", "llm", "neural", "training",
        "inference", "embedding", "vector", "eidolon",
        "transformer", "gpt", "openai", "anthropic", "claude",
    ],
    "Software Development": [
        "code", "python", "function", "class", "import",
        "git", "vscode", "cursor", "debug", "test", "build",
        "api", "fastapi", "typescript", "javascript", "react",
        "next", "node", "flask", "django",
    ],
    "Web & Research":       [
        "browser", "chrome", "firefox", "edge", "http",
        "url", "search", "stackoverflow", "docs", "github",
        "documentation", "tutorial",
    ],
    "Documents & Writing":  [
        "pdf", "word", "document", "notion", "obsidian",
        "note", "write", "report", "draft", "essay",
    ],
    "System & DevOps":      [
        "terminal", "shell", "bash", "powershell", "docker",
        "deploy", "server", "linux", "npm", "pip", "conda",
        "kubernetes", "aws", "gcp", "azure",
    ],
    "Communication":        [
        "slack", "email", "teams", "discord", "meeting",
        "chat", "message", "zoom", "meet", "call",
    ],
}

_DOMAIN_COLORS: dict[str, str] = {
    "Camera & Vision":      "#00b4ff",
    "AI & ML":              "#a78bfa",
    "Software Development": "#22c55e",
    "Web & Research":       "#eab308",
    "Documents & Writing":  "#f97316",
    "System & DevOps":      "#06b6d4",
    "Communication":        "#ec4899",
    "Other":                "#4a5568",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _item_text(item: dict) -> str:
    meta = item.get("metadata") or {}
    parts = [
        item.get("title", ""),
        item.get("text", "")[:300],
        item.get("source", ""),
        item.get("type", ""),
        meta.get("app_name", ""),
        meta.get("dominant_app", ""),
        meta.get("scene_type", ""),
        meta.get("probable_task", ""),
        meta.get("workflow_type", ""),
    ]
    return " ".join(p for p in parts if p).lower()


def _score_item(item: dict) -> dict[str, int]:
    """Return per-domain keyword-hit counts for one memory item."""
    text = _item_text(item)
    scores: dict[str, int] = {}
    for domain, keywords in DOMAINS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits:
            scores[domain] = hits
    return scores


def _primary_domain(item: dict) -> str:
    scores = _score_item(item)
    if not scores:
        return "Other"
    return max(scores, key=lambda d: scores[d])


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def cluster_memories(memories: list[dict]) -> list[dict[str, Any]]:
    """
    Assign each memory to its primary domain and return cluster statistics.
    """
    buckets: dict[str, list[dict]] = defaultdict(list)
    for m in memories:
        buckets[_primary_domain(m)].append(m)

    total = len(memories) or 1
    clusters: list[dict] = []

    for domain in list(DOMAINS.keys()) + ["Other"]:
        items = buckets.get(domain, [])
        if not items:
            continue
        recent_sorted = sorted(
            items, key=lambda x: x.get("created_at", ""), reverse=True
        )
        clusters.append({
            "name":         domain,
            "color":        _DOMAIN_COLORS.get(domain, "#4a5568"),
            "count":        len(items),
            "percentage":   round(len(items) / total * 100),
            "recent_title": recent_sorted[0].get("title", "") if recent_sorted else "",
        })

    return sorted(clusters, key=lambda c: c["count"], reverse=True)


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

def analyze_timeline(memories: list[dict]) -> dict[str, Any]:
    """
    Compute daily activity counts, week-over-week trends, and domain trends.
    Returns 14 days of daily data plus aggregate statistics.
    """
    now   = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Group memories by ISO date string
    daily_buckets: dict[str, list[dict]] = defaultdict(list)
    for m in memories:
        ts = _parse_ts(m.get("created_at"))
        if ts:
            daily_buckets[ts.strftime("%Y-%m-%d")].append(m)

    # Build 14-day series
    daily: list[dict] = []
    for i in range(13, -1, -1):
        day     = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        items   = daily_buckets.get(day, [])
        dom_cnt: dict[str, int] = defaultdict(int)
        for m in items:
            dom_cnt[_primary_domain(m)] += 1
        daily.append({
            "date":    day,
            "label":   (today - timedelta(days=i)).strftime("%a"),
            "count":   len(items),
            "domains": dict(dom_cnt),
        })

    # Week boundaries: days[0..6] = last week, days[7..13] = this week
    last_week_items = [m for row in daily[:7]  for m in daily_buckets.get(row["date"], [])]
    this_week_items = [m for row in daily[7:]  for m in daily_buckets.get(row["date"], [])]
    this_wk = len(this_week_items)
    last_wk = len(last_week_items)

    if last_wk > 0:
        wow_pct   = round((this_wk - last_wk) / last_wk * 100)
        wow_label = (f"+{wow_pct}%" if wow_pct >= 0 else f"{wow_pct}%")
    elif this_wk > 0:
        wow_label = "new this week"
    else:
        wow_label = "no recent activity"

    # Domain trends: compare this week vs last week
    this_domains: Counter = Counter(_primary_domain(m) for m in this_week_items)
    last_domains: Counter = Counter(_primary_domain(m) for m in last_week_items)
    trending: list[dict] = []
    for domain in sorted(set(list(this_domains) + list(last_domains))):
        curr = this_domains.get(domain, 0)
        prev = last_domains.get(domain, 0)
        if curr == 0:
            continue
        if prev == 0:
            trend, delta = "new",     f"+{curr}"
        elif curr > prev:
            pct = round((curr - prev) / prev * 100)
            trend, delta = "rising",  f"+{pct}%"
        elif curr < prev:
            pct = round((prev - curr) / prev * 100)
            trend, delta = "falling", f"-{pct}%"
        else:
            trend, delta = "stable",  "→"
        trending.append({
            "domain":     domain,
            "color":      _DOMAIN_COLORS.get(domain, "#4a5568"),
            "this_week":  curr,
            "last_week":  prev,
            "trend":      trend,
            "delta":      delta,
        })
    trending.sort(key=lambda x: x["this_week"], reverse=True)

    # Best single day
    best = max(daily, key=lambda r: r["count"]) if daily else None

    return {
        "daily":            daily,
        "this_week_count":  this_wk,
        "last_week_count":  last_wk,
        "wow_change":       wow_label,
        "trending_domains": trending[:6],
        "best_day":         best["date"]  if best else None,
        "best_day_count":   best["count"] if best else 0,
        "best_day_label":   best["label"] if best else "",
        "total_memories":   len(memories),
    }


# ---------------------------------------------------------------------------
# Proactive insights
# ---------------------------------------------------------------------------

def generate_insights(memories: list[dict]) -> list[dict[str, Any]]:
    """
    Produce proactive, auto-generated insights from memory patterns.
    Each insight: { type, title, text, value }
    """
    if not memories:
        return []

    insights: list[dict] = []
    clusters  = cluster_memories(memories)
    timeline  = analyze_timeline(memories)
    total     = len(memories) or 1

    # 1. Dominant domain
    if clusters:
        top = clusters[0]
        insights.append({
            "type":  "dominant",
            "title": "Most Active Area",
            "text":  f"{top['name']} appears in {top['percentage']}% of your captured memories.",
            "value": f"{top['percentage']}%",
            "color": top.get("color", "#00b4ff"),
        })

    # 2. Week-over-week
    if timeline["this_week_count"] > 0:
        insights.append({
            "type":  "trend",
            "title": "This Week vs Last Week",
            "text":  (
                f"{timeline['this_week_count']} memories captured this week "
                f"({timeline['wow_change']} vs last week)."
            ),
            "value": timeline["wow_change"],
            "color": "#22c55e" if "+" in timeline["wow_change"] else "#eab308",
        })

    # 3. Rising domain
    rising = [d for d in timeline["trending_domains"] if d["trend"] == "rising"]
    if rising:
        r = rising[0]
        insights.append({
            "type":  "rising",
            "title": "Increasing Focus",
            "text":  f"{r['domain']} activity is trending up ({r['delta']} this week).",
            "value": r["delta"],
            "color": r.get("color", "#a78bfa"),
        })

    # 4. Memory span
    timestamps = [_parse_ts(m.get("created_at")) for m in memories]
    timestamps = [t for t in timestamps if t]
    if len(timestamps) >= 2:
        span_days = (max(timestamps) - min(timestamps)).days
        if span_days >= 1:
            insights.append({
                "type":  "span",
                "title": "Memory Span",
                "text":  (
                    f"Memory database spans {span_days} day{'s' if span_days != 1 else ''} "
                    f"with {total} captured events total."
                ),
                "value": f"{span_days}d",
                "color": "#06b6d4",
            })

    # 5. Primary source
    sources: Counter = Counter(m.get("source", "unknown") for m in memories)
    if sources:
        src, cnt = sources.most_common(1)[0]
        insights.append({
            "type":  "source",
            "title": "Primary Capture Source",
            "text":  f"'{src}' is the most active source ({round(cnt/total*100)}% of memories).",
            "value": src,
            "color": "#f97316",
        })

    # 6. Best day
    if timeline["best_day_count"] > 1:
        insights.append({
            "type":  "peak",
            "title": "Most Active Day",
            "text":  (
                f"{timeline['best_day_label']} {timeline['best_day']} was your most active day "
                f"with {timeline['best_day_count']} memories captured."
            ),
            "value": f"{timeline['best_day_count']} mem",
            "color": "#eab308",
        })

    return insights


# ---------------------------------------------------------------------------
# Profile context builder
# ---------------------------------------------------------------------------

def build_profile_context(memories: list[dict]) -> dict[str, Any]:
    """
    Run all analysis passes and return a unified profile context dict.
    The 'summary' field is filled by the caller (Gemini or local fallback).
    """
    from app.services.profile_service import get_profile

    clusters  = cluster_memories(memories)
    timeline  = analyze_timeline(memories)
    insights  = generate_insights(memories)
    base_prof = get_profile(memories)

    # Aggregate domain scores across all memories
    all_hits: Counter = Counter()
    for m in memories:
        for domain, hits in _score_item(m).items():
            all_hits[domain] += hits
    total_hits = sum(all_hits.values()) or 1
    domain_scores = [
        {
            "domain":     d,
            "score":      round(c / total_hits, 2),
            "percentage": round(c / total_hits * 100),
            "count":      c,
            "color":      _DOMAIN_COLORS.get(d, "#4a5568"),
        }
        for d, c in all_hits.most_common()
        if c > 0
    ]

    primary_activities = [ds["domain"] for ds in domain_scores[:3]]
    interests          = [ds["domain"] for ds in domain_scores[:5]]
    active_projects    = _infer_projects(memories, domain_scores, base_prof)

    work_patterns = {
        "peak_period":      base_prof.get("peak_period", ""),
        "top_apps":         [a["app"] for a in (base_prof.get("top_apps") or [])[:4]],
        "workflow_summary": base_prof.get("workflow_summary", ""),
    }

    confidence = min(1.0, len(memories) / 15.0)

    return {
        "summary":            "",          # filled by Gemini or local synthesis
        "gemini_powered":     False,
        "primary_activities": primary_activities,
        "interests":          interests,
        "active_projects":    active_projects,
        "work_patterns":      work_patterns,
        "dominant_themes":    [ds["domain"] for ds in domain_scores[:4]],
        "domain_scores":      domain_scores,
        "top_sources":        [s for s, _ in Counter(m.get("source","") for m in memories).most_common(4) if s],
        "keywords":           base_prof.get("top_keywords", [])[:10],
        "memory_count":       len(memories),
        "confidence":         round(confidence, 2),
        "clusters":           clusters,
        "timeline":           timeline,
        "insights":           insights,
    }


def _infer_projects(
    memories: list[dict],
    domain_scores: list[dict],
    base_prof: dict,
) -> list[str]:
    """Infer active project names from keyword and domain patterns."""
    projects: list[str] = []
    all_text  = " ".join(_item_text(m) for m in memories[:40])
    keywords  = [k.lower() for k in (base_prof.get("top_keywords") or [])[:10]]
    top_domains = [ds["domain"] for ds in domain_scores[:3]]

    if "eidolon" in all_text:
        projects.append("EIDOLON OS")
    if "Camera & Vision" in top_domains:
        projects.append("Camera Monitoring System")
    if "AI & ML" in top_domains:
        projects.append("AI / ML Development")
    if "Software Development" in top_domains and "EIDOLON OS" not in projects:
        projects.append("Software Development")

    # Fall back to prominent keywords if we found nothing
    if not projects:
        for kw in keywords[:3]:
            if len(kw) > 3 and kw not in {"code", "work", "test", "new", "open", "file"}:
                projects.append(kw.title())

    return (projects or ["Active Work"])[:4]


# ---------------------------------------------------------------------------
# Local profile summary (Gemini unavailable)
# ---------------------------------------------------------------------------

def local_profile_summary(ctx: dict[str, Any]) -> str:
    """Rule-based cognitive summary when Gemini is unavailable."""
    activities = ctx.get("primary_activities", [])
    projects   = ctx.get("active_projects", [])
    n          = ctx.get("memory_count", 0)

    if not activities:
        return (
            f"Your EIDOLON OS has captured {n} memories. "
            "Capture more activity for a detailed cognitive profile."
        )

    act_str  = " and ".join(activities[:2])
    proj_str = f", with a focus on {projects[0]}" if projects else ""

    return (
        f"Based on {n} captured memories, you appear to be actively working on "
        f"{act_str}{proj_str}. "
        f"Recurring themes in your activity suggest a strong technical focus across "
        f"{', '.join(activities[:3])}. "
        f"EIDOLON OS will refine this profile as more memories are captured."
    )
