"""
Intelligence endpoints — Phase 21.

GET /intelligence/profile   Cognitive profile (Gemini-synthesised)
GET /intelligence/timeline  14-day trend analysis + domain breakdowns
GET /intelligence/clusters  Memory clusters by domain
GET /intelligence/insights  Proactive auto-generated insights

All endpoints are read-only and privacy-first — no raw memory text is
returned, only aggregated statistics and synthesised summaries.
"""

import logging

from fastapi import APIRouter

from app.services import intelligence_service as intel
from app.services.memory_store import memory_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/intelligence", tags=["intelligence"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _synthesise_profile(ctx: dict) -> str:
    """Ask Gemini to write a cognitive profile paragraph from the analysis."""
    try:
        from app.services.gemini_bridge_service import get_gemini_service
        svc = get_gemini_service()
        if not svc.is_active():
            return intel.local_profile_summary(ctx)

        domains   = ", ".join(ctx.get("primary_activities", []) or ["varied work"])
        projects  = ", ".join(ctx.get("active_projects",    []) or ["active development"])
        apps      = ", ".join(ctx.get("work_patterns", {}).get("top_apps", []) or [])
        keywords  = ", ".join(ctx.get("keywords", [])[:6])
        n         = ctx.get("memory_count", 0)
        tl        = ctx.get("timeline", {})
        this_week = tl.get("this_week_count", 0)
        wow       = tl.get("wow_change", "")

        prompt = (
            f"You are EIDOLON OS — a cognitive operating system. "
            f"Based on the following memory analysis of {n} captured events, "
            f"write a 3–5 sentence cognitive profile of this user. "
            f"Use second person ('You appear to be...', 'Based on your memories...'). "
            f"Be specific and insightful. Do NOT use bullet points or lists.\n\n"
            f"Domain focus:        {domains}\n"
            f"Active projects:     {projects}\n"
            f"Top apps used:       {apps or 'not detected'}\n"
            f"Recurring keywords:  {keywords or 'none'}\n"
            f"Activity this week:  {this_week} events ({wow})\n\n"
            f"Cognitive profile paragraph:"
        )

        text = svc.generate_from_prompt(prompt, max_tokens=350)
        return text if text else intel.local_profile_summary(ctx)

    except Exception as exc:
        logger.warning("intelligence: Gemini profile synthesis failed — %s", exc)
        return intel.local_profile_summary(ctx)


def _synthesise_timeline_narrative(tl: dict) -> str:
    """Ask Gemini for a one-paragraph timeline summary."""
    try:
        from app.services.gemini_bridge_service import get_gemini_service
        svc = get_gemini_service()
        if not svc.is_active():
            return _local_timeline_narrative(tl)

        rising    = [d for d in tl.get("trending_domains", []) if d["trend"] == "rising"]
        stable    = [d for d in tl.get("trending_domains", []) if d["trend"] == "stable"]
        rising_s  = ", ".join(d["domain"] for d in rising[:2]) or "none"
        stable_s  = ", ".join(d["domain"] for d in stable[:2]) or "none"
        this_wk   = tl.get("this_week_count", 0)
        last_wk   = tl.get("last_week_count", 0)
        wow       = tl.get("wow_change", "")
        best_day  = tl.get("best_day_label", "")
        best_cnt  = tl.get("best_day_count", 0)

        prompt = (
            f"You are EIDOLON OS. Write a 2–3 sentence timeline summary.\n"
            f"This week: {this_wk} events ({wow} vs last week: {last_wk})\n"
            f"Rising topics: {rising_s}\n"
            f"Stable topics: {stable_s}\n"
            f"Peak day: {best_day} with {best_cnt} events\n"
            f"Use second person. Be specific. No bullet points."
        )

        text = svc.generate_from_prompt(prompt, max_tokens=200)
        return text if text else _local_timeline_narrative(tl)

    except Exception as exc:
        logger.warning("intelligence: Gemini timeline narrative failed — %s", exc)
        return _local_timeline_narrative(tl)


def _local_timeline_narrative(tl: dict) -> str:
    this_wk = tl.get("this_week_count", 0)
    wow     = tl.get("wow_change", "")
    rising  = [d["domain"] for d in tl.get("trending_domains", []) if d["trend"] == "rising"]
    best    = tl.get("best_day_label", "")
    best_n  = tl.get("best_day_count", 0)

    parts = []
    if this_wk:
        parts.append(f"You captured {this_wk} memories this week ({wow} vs last week).")
    if rising:
        parts.append(f"{rising[0]} activity is trending upward.")
    if best and best_n > 1:
        parts.append(f"{best} was your most active day with {best_n} events.")
    return " ".join(parts) or "Not enough recent data for trend analysis yet."


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/profile")
async def get_cognitive_profile():
    """
    Cognitive profile — domain focus, active projects, interests, and
    a Gemini-synthesised natural-language summary paragraph.
    """
    memories = memory_store.list()
    ctx      = intel.build_profile_context(memories)
    summary  = _synthesise_profile(ctx)
    ctx["summary"]       = summary
    ctx["gemini_powered"] = bool(summary and len(summary) > 60)
    return ctx


@router.get("/timeline")
async def get_timeline_intelligence():
    """
    14-day daily activity breakdown with week-over-week trend analysis
    and a Gemini-synthesised narrative summary.
    """
    memories  = memory_store.list()
    tl        = intel.analyze_timeline(memories)
    tl["narrative"] = _synthesise_timeline_narrative(tl)
    return tl


@router.get("/clusters")
async def get_memory_clusters():
    """Memory clusters grouped by domain with percentages."""
    memories = memory_store.list()
    return {"clusters": intel.cluster_memories(memories)}


@router.get("/insights")
async def get_proactive_insights():
    """Auto-generated proactive insights from memory patterns."""
    memories = memory_store.list()
    return {"insights": intel.generate_insights(memories)}
