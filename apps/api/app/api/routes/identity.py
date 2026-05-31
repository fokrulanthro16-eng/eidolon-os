"""
Identity endpoints — Phase 22.

GET /identity/profile  Full identity profile (Gemini-synthesised)
GET /identity/projects Active project list
GET /identity/next     "What should I work on next?" suggestion

Answers the questions a cognitive OS should always be able to answer:
  Who am I?   What am I building?   What are my active projects?
  What are my goals?   What should I work on next?
"""

import logging

from fastapi import APIRouter

from app.services import identity_service as ident
from app.services.memory_store import memory_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/identity", tags=["identity"])


# ---------------------------------------------------------------------------
# Gemini synthesis helpers
# ---------------------------------------------------------------------------

def _synthesise_user_summary(ctx: dict) -> str:
    """Ask Gemini to write a 3-4 sentence identity paragraph."""
    try:
        from app.services.gemini_bridge_service import get_gemini_service
        svc = get_gemini_service()
        if not svc.is_active():
            return ident.local_identity_summary(ctx)

        projects  = ", ".join(p["name"] for p in ctx.get("active_projects", [])[:3])
        focus     = ctx.get("current_focus", "")
        goals     = "; ".join(ctx.get("inferred_goals", [])[:3])
        domains   = ", ".join(ctx.get("technical_domains", []))
        n         = ctx.get("memory_count", 0)

        prompt = (
            f"You are EIDOLON OS — a cognitive operating system. "
            f"Based on the following analysis of {n} captured memories, "
            f"write a 3–4 sentence identity profile of the user. "
            f"Use second person ('You appear to be...', 'Based on your activity...'). "
            f"Be specific and insightful. Do NOT use bullet points.\n\n"
            f"Active projects:     {projects or 'none detected'}\n"
            f"Current focus:       {focus or 'not determined'}\n"
            f"Inferred goals:      {goals or 'none inferred'}\n"
            f"Technical domains:   {domains or 'varied'}\n\n"
            f"Identity paragraph:"
        )

        text = svc.generate_from_prompt(prompt, max_tokens=280)
        return text if text else ident.local_identity_summary(ctx)

    except Exception as exc:
        logger.warning("identity: Gemini synthesis failed — %s", exc)
        return ident.local_identity_summary(ctx)


def _synthesise_next(ctx: dict) -> str:
    """Ask Gemini to suggest the most impactful next action."""
    try:
        from app.services.gemini_bridge_service import get_gemini_service
        svc = get_gemini_service()
        if not svc.is_active():
            return ctx.get("suggested_next", "")

        projects = ", ".join(p["name"] for p in ctx.get("active_projects", [])[:3] if p.get("status") == "active")
        focus    = ctx.get("current_focus", "")
        goals    = "; ".join(ctx.get("inferred_goals", [])[:2])

        prompt = (
            f"You are EIDOLON OS. Given a user with:\n"
            f"Active projects: {projects}\n"
            f"Current focus:   {focus}\n"
            f"Goals:           {goals}\n\n"
            f"Write ONE specific sentence recommending what they should work on next. "
            f"Be direct and actionable. Start with 'You should...' or 'Continue...'."
        )

        text = svc.generate_from_prompt(prompt, max_tokens=100)
        return text if text else ctx.get("suggested_next", "")

    except Exception as exc:
        logger.warning("identity: next suggestion failed — %s", exc)
        return ctx.get("suggested_next", "")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/profile")
async def get_identity_profile():
    """
    Full identity profile: Gemini summary, active projects, goals,
    current focus, and what to work on next.
    """
    memories = memory_store.list()
    ctx      = ident.get_or_build(memories)
    summary  = _synthesise_user_summary(ctx)
    ctx["user_summary"]   = summary
    ctx["gemini_powered"] = bool(summary and len(summary) > 60)
    ctx["suggested_next"] = _synthesise_next(ctx)
    _save_back(ctx)
    return ctx


@router.get("/projects")
async def get_active_projects():
    """Active project list with status and confidence."""
    memories = memory_store.list()
    ctx      = ident.get_or_build(memories)
    return {
        "projects":      ctx.get("active_projects", []),
        "current_focus": ctx.get("current_focus", ""),
        "memory_count":  ctx.get("memory_count", 0),
    }


@router.get("/next")
async def get_next_suggestion():
    """'What should I work on next?' — Gemini-powered suggestion."""
    memories = memory_store.list()
    ctx      = ident.get_or_build(memories)
    return {
        "suggestion":   _synthesise_next(ctx),
        "focus":        ctx.get("current_focus", ""),
        "top_project":  ctx["active_projects"][0]["name"] if ctx.get("active_projects") else "",
    }


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _save_back(ctx: dict) -> None:
    try:
        ident._save_cache(ctx)
    except Exception:
        pass
