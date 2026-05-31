"""
Identity Engine — Phase 22.

Builds and persists a user identity from accumulated memories.
Detects active projects, infers goals and current focus, stores the
result in storage/identity-db/identity.json with a 30-minute TTL.

Designed to answer:
  Who am I?          What am I building?     What are my active projects?
  What are my goals? What should I work on next?
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _identity_file() -> Path:
    from app.core.config import STORAGE_DIR
    d = STORAGE_DIR / "identity-db"
    d.mkdir(parents=True, exist_ok=True)
    return d / "identity.json"


# ---------------------------------------------------------------------------
# Project detection — ordered by priority
# ---------------------------------------------------------------------------

PROJECT_PATTERNS: dict[str, list[str]] = {
    "EIDOLON OS": [
        "eidolon", "cognitive os", "memory store", "brain chat",
        "screen watcher", "memory-db", "intelligence_service",
        "phase 2", "phase 21", "phase 22",
    ],
    "Gemini Hybrid Layer": [
        "gemini", "aistudio", "brain_provider", "geminibridgeservice",
        "generate_with_history", "llm hybrid", "quota",
    ],
    "Camera & Vision System": [
        "camera", "cctv", "yolo", "person detected", "object stationary",
        "live_camera", "video analysis", "object detection",
    ],
    "AI / ML Development": [
        "model", "training", "neural", "embedding", "vector",
        "transformer", "inference", "dataset",
    ],
    "Web / Frontend": [
        "react", "next", "typescript", "component", "page.tsx",
        "npm", "frontend", "tailwind",
    ],
    "Python Backend": [
        "fastapi", "uvicorn", "route", "endpoint", "pydantic",
        "requirements.txt", "pip install",
    ],
    "Research & Documents": [
        "pdf", "paper", "research", "document", "notes", "markdown",
    ],
}

# ---------------------------------------------------------------------------
# Goal inference — (goal text, trigger keywords)
# ---------------------------------------------------------------------------

GOAL_PATTERNS: list[tuple[str, list[str]]] = [
    ("Build a local-first AI cognitive OS",       ["eidolon", "memory", "cognitive", "screen watcher"]),
    ("Integrate Google Gemini for cloud reasoning",["gemini", "llm", "aistudio", "brain_provider"]),
    ("Implement camera monitoring & vision",       ["camera", "cctv", "yolo", "detection"]),
    ("Win the Google AI First Challenge",          ["google", "challenge", "submission", "demo script"]),
    ("Build privacy-preserving AI tools",         ["local", "privacy", "offline", "no cloud"]),
    ("Develop an agentic AI workflow",             ["agent", "tool_call", "function_calling", "agentic"]),
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _item_text(item: dict) -> str:
    meta = item.get("metadata") or {}
    return " ".join(filter(None, [
        item.get("title", ""),
        item.get("text", "")[:300],
        item.get("source", ""),
        meta.get("app_name", ""),
        meta.get("probable_task", ""),
    ])).lower()


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _days_ago(dt: datetime) -> float:
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400


# ---------------------------------------------------------------------------
# Project detection
# ---------------------------------------------------------------------------

def _detect_projects(memories: list[dict]) -> list[dict[str, Any]]:
    """
    Score each project pattern against all memories.
    Returns projects sorted by confidence (descending), with evidence.
    """
    hits: dict[str, list[str]] = defaultdict(list)
    last_seen: dict[str, datetime] = {}

    for m in memories:
        text = _item_text(m)
        ts   = _parse_ts(m.get("created_at"))
        for project, keywords in PROJECT_PATTERNS.items():
            matched = [kw for kw in keywords if kw in text]
            if matched:
                hits[project].extend(matched)
                if ts and (project not in last_seen or ts > last_seen[project]):
                    last_seen[project] = ts

    total = len(memories) or 1
    projects: list[dict] = []
    for project, matched_kws in hits.items():
        # Confidence: unique keyword hits / total keywords, weighted by memory count
        unique_hit_kws  = len(set(matched_kws))
        total_kws       = len(PROJECT_PATTERNS[project])
        coverage        = min(unique_hit_kws / total_kws, 1.0)
        frequency       = min(len(matched_kws) / (total * 0.5), 1.0)
        confidence      = round((coverage * 0.6 + frequency * 0.4), 2)

        ls = last_seen.get(project)
        days = _days_ago(ls) if ls else 999

        status = "active" if days <= 7 else "recent" if days <= 30 else "dormant"

        projects.append({
            "name":          project,
            "confidence":    confidence,
            "status":        status,
            "last_seen":     ls.strftime("%Y-%m-%d") if ls else "",
            "days_inactive": round(days, 1),
            "evidence_count": len(set(matched_kws)),
        })

    return sorted(projects, key=lambda p: (-{"active": 3, "recent": 2, "dormant": 1}[p["status"]], -p["confidence"]))


# ---------------------------------------------------------------------------
# Current focus
# ---------------------------------------------------------------------------

def _infer_focus(memories: list[dict]) -> str:
    """Determine what the user is focused on in the last 48 hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    recent = [
        m for m in memories
        if (ts := _parse_ts(m.get("created_at"))) and ts >= cutoff
    ]

    if not recent:
        # Fall back to last 7 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        recent = [
            m for m in memories
            if (ts := _parse_ts(m.get("created_at"))) and ts >= cutoff
        ]

    if not recent:
        return ""

    # Score project patterns against recent memories
    focus_hits: Counter = Counter()
    for m in recent:
        text = _item_text(m)
        for project, keywords in PROJECT_PATTERNS.items():
            for kw in keywords:
                if kw in text:
                    focus_hits[project] += 1

    if focus_hits:
        return focus_hits.most_common(1)[0][0]
    return ""


# ---------------------------------------------------------------------------
# Goal inference
# ---------------------------------------------------------------------------

def _infer_goals(memories: list[dict]) -> list[str]:
    """Infer user goals from keyword patterns across all memories."""
    all_text = " ".join(_item_text(m) for m in memories)
    goals: list[str] = []
    for goal_text, triggers in GOAL_PATTERNS:
        if any(kw in all_text for kw in triggers):
            goals.append(goal_text)
    return goals[:5]


# ---------------------------------------------------------------------------
# "What next" suggestion
# ---------------------------------------------------------------------------

def _suggest_next(projects: list[dict], focus: str) -> str:
    """Suggest the most productive next task based on active projects."""
    active = [p for p in projects if p["status"] == "active"]
    if not active:
        return "No active projects detected. Capture more activity for suggestions."

    primary = active[0]["name"]
    if focus and focus != primary:
        return f"Continue work on {primary}, with focus on {focus}."
    return f"Continue your active work on {primary}."


# ---------------------------------------------------------------------------
# Full context builder
# ---------------------------------------------------------------------------

def build_identity_context(memories: list[dict]) -> dict[str, Any]:
    """
    Run all identity analysis passes and return a unified context dict.
    The 'user_summary' field is empty — callers fill it via Gemini synthesis.
    """
    projects      = _detect_projects(memories)
    focus         = _infer_focus(memories)
    goals         = _infer_goals(memories)
    suggested     = _suggest_next(projects, focus)

    # Technical domains from project types
    active_project_names = [p["name"] for p in projects if p["status"] in ("active", "recent")]
    technical_domains: list[str] = []
    if any("Camera" in n or "Vision" in n for n in active_project_names):
        technical_domains.append("Camera & Vision Systems")
    if any("Gemini" in n or "AI" in n for n in active_project_names):
        technical_domains.append("AI / ML Engineering")
    if any("EIDOLON" in n or "Backend" in n for n in active_project_names):
        technical_domains.append("Software Development")
    if any("Research" in n or "Document" in n for n in active_project_names):
        technical_domains.append("Research & Documentation")

    confidence = min(1.0, len(memories) / 12.0)

    return {
        "user_summary":      "",           # filled by Gemini or local fallback
        "gemini_powered":    False,
        "active_projects":   projects,
        "current_focus":     focus,
        "inferred_goals":    goals,
        "suggested_next":    suggested,
        "technical_domains": technical_domains,
        "confidence":        round(confidence, 2),
        "memory_count":      len(memories),
        "last_updated":      datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Local (non-Gemini) summary
# ---------------------------------------------------------------------------

def local_identity_summary(ctx: dict[str, Any]) -> str:
    """Rule-based identity paragraph when Gemini is unavailable."""
    projects = [p["name"] for p in ctx.get("active_projects", [])[:3] if p.get("status") in ("active", "recent")]
    # EIDOLON OS is the parent project — always lead with it
    projects.sort(key=lambda n: (0 if "EIDOLON" in n else 1))
    focus    = ctx.get("current_focus", "")
    goals    = ctx.get("inferred_goals", [])
    n        = ctx.get("memory_count", 0)

    if not projects:
        return (
            f"Your EIDOLON OS has captured {n} memories. "
            "Add more activity to build a detailed identity profile."
        )

    proj_str = " and ".join(projects[:2])
    goal_str = f" with the goal to {goals[0].lower()}" if goals else ""
    return (
        f"Based on {n} captured memories, you appear to be a developer "
        f"actively working on {proj_str}{goal_str}. "
        f"Your activity shows a strong focus on building intelligent, "
        f"privacy-first software systems."
    )


# ---------------------------------------------------------------------------
# Persistent cache
# ---------------------------------------------------------------------------

_CACHE_TTL_MINUTES = 30


def _load_cache() -> dict | None:
    """Load cached identity if it exists and is within TTL."""
    try:
        path = _identity_file()
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        updated = datetime.fromisoformat(data.get("last_updated", "2000-01-01T00:00:00+00:00"))
        if (datetime.now(timezone.utc) - updated) < timedelta(minutes=_CACHE_TTL_MINUTES):
            return data
    except Exception as exc:
        logger.debug("identity: cache read failed — %s", exc)
    return None


def _save_cache(data: dict) -> None:
    try:
        path = _identity_file()
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.debug("identity: cache write failed — %s", exc)


def get_or_build(memories: list[dict]) -> dict[str, Any]:
    """
    Return cached identity context if fresh, otherwise rebuild.
    Does NOT synthesise the user_summary — callers handle that.
    """
    cached = _load_cache()
    if cached and cached.get("memory_count") == len(memories):
        return cached
    ctx = build_identity_context(memories)
    _save_cache(ctx)
    return ctx
