"""
Vision Intelligence Service — Phase 11 enhanced scene analysis.

Extends vision_service.py with:
  - Browser-content fingerprinting (Claude, GitHub, Swagger, ChatGPT, etc.)
  - Programming language / framework detection
  - probable_task natural-language description
  - active_tools list
  - confidence score
  - smart_title for better memory labels

Output (superset of vision_service schema):
    dominant_app   str         resolved app name
    scene_type     str         same enum as vision_service
    workflow_type  str         same enum as vision_service
    visual_tags    list[str]   up to 10 tags
    confidence     float       0.0–1.0
    active_tools   list[str]   detected tools / frameworks / languages
    probable_task  str         "User editing Next.js frontend"
    smart_title    str         "VSCode Frontend Editing"
    ui_layout      str         same as vision_service
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Browser content fingerprints — checked against OCR + window title
# ---------------------------------------------------------------------------

_BROWSER_FINGERPRINTS: list[tuple[str, str, list[str]]] = [
    # (scene_label, task_label, patterns)
    ("swagger-ui",       "API testing",            [r"swagger\s*ui\b", r"\bSwagger\b", r"localhost:\d+/docs", r"\bOpenAPI\b", r"Try it out"]),
    ("github",           "code review",             [r"github\.com", r"\bPull request\b", r"\bCommit\b.*\bpush\b", r"\bpull request\b", r"\bfork\b.*\bgit\b"]),
    ("claude-ai",        "AI research",             [r"claude\.ai", r"\bClaude\b.*\bAnthropic\b", r"anthropic\.com"]),
    ("chatgpt",          "AI research",             [r"chatgpt\.com", r"chat\.openai\.com", r"\bChatGPT\b"]),
    ("gemini",           "AI research",             [r"gemini\.google\.com", r"\bGoogle\s+Gemini\b"]),
    ("arxiv",            "paper reading",           [r"arxiv\.org", r"\barXiv\b"]),
    ("stackoverflow",    "debugging research",      [r"stackoverflow\.com", r"\bStack Overflow\b"]),
    ("localhost-3000",   "frontend preview",        [r"localhost:3000", r"127\.0\.0\.1:3000"]),
    ("localhost-8010",   "API testing",             [r"localhost:8010", r"127\.0\.0\.1:8010"]),
    ("youtube-research", "video watching",          [r"youtube\.com/watch", r"\bYouTube\b"]),
    ("pdf-viewer",       "document reading",        [r"\.pdf\b", r"\bAdobe\b.*PDF", r"\bPDF\s+Reader\b"]),
    ("npm-registry",     "package research",        [r"npmjs\.com", r"\bnpm\s+install\b"]),
    ("pypi",             "package research",        [r"pypi\.org", r"\bpip\s+install\b"]),
    ("docs-site",        "documentation reading",   [r"docs\.\w+\.com", r"\bAPI\s+Reference\b", r"\bGetting\s+Started\b"]),
    ("file-explorer",    "file management",         [r"\bThis PC\b", r"\bLocal Disk\b", r"\bQuick access\b"]),
    ("cctv-dashboard",   "surveillance review",     [r"\bCCTV\b", r"\bmotion detected\b", r"\bcamera\s+event\b", r"EIDOLON\s+OS"]),
]

# ---------------------------------------------------------------------------
# Programming language / framework detection
# ---------------------------------------------------------------------------

_LANG_PATTERNS: list[tuple[str, list[str]]] = [
    ("Python",     [r"\bdef \w+\s*\(", r"^from \w+ import", r"^import \w+", r"\bif __name__\s*==", r"\.py\b"]),
    ("TypeScript", [r"\binterface \w+", r"\btype \w+\s*=", r"\.tsx?\b", r"\bconst \w+:\s*\w+"]),
    ("JavaScript", [r"\bconst \w+\s*=", r"\bfunction\s+\w+\s*\(", r"require\s*\(", r"\.js\b"]),
    ("React",      [r"\bReact\b", r"import React", r"<\w+Component", r"useState\s*\(", r"useEffect\s*\("]),
    ("Next.js",    [r"\bNext\.js\b", r"next/\w+", r"getServerSideProps", r"getStaticProps"]),
    ("FastAPI",    [r"\bFastAPI\b", r"@app\.(?:get|post|put|delete)", r"uvicorn", r"from fastapi"]),
    ("CSS",        [r"\.css\b", r"\{.*color\s*:", r"margin\s*:", r"padding\s*:", r"@media\s*\("]),
    ("SQL",        [r"\bSELECT\b.*\bFROM\b", r"\bINSERT\s+INTO\b", r"\bCREATE\s+TABLE\b"]),
    ("Docker",     [r"\bDockerfile\b", r"\bdocker\s+\w+", r"\bFROM\s+\w+"]),
    ("Git",        [r"\bgit\s+(?:add|commit|push|pull|status|log)\b", r"\bmerge\b.*\bbranch\b"]),
]

# ---------------------------------------------------------------------------
# App-specific probable_task and smart_title generators
# ---------------------------------------------------------------------------

_PROBABLE_TASKS: dict[str, str] = {
    "debugging":            "debugging code",
    "coding":               "editing code",
    "terminal-work":        "running terminal commands",
    "browser-research":     "web research",
    "ai-chat":              "researching with AI",
    "documentation":        "reading documentation",
    "api-testing":          "testing API endpoints",
    "communication":        "team communication",
    "design":               "working in design tool",
    "video-watching":       "watching video content",
    "surveillance-review":  "reviewing surveillance footage",
    "pdf-reading":          "reading PDF document",
}


def _detect_browser_context(ocr_text: str, window_title: str | None) -> tuple[str | None, str | None, list[str]]:
    """Return (browser_scene, activity, matched_tools) from OCR + window title."""
    combined = (ocr_text or "") + " " + (window_title or "")
    for scene_label, activity, patterns in _BROWSER_FINGERPRINTS:
        for pat in patterns:
            if re.search(pat, combined, re.IGNORECASE | re.MULTILINE):
                return scene_label, activity, [scene_label]
    return None, None, []


def _detect_languages(ocr_text: str) -> list[str]:
    """Detect programming languages / frameworks from OCR text."""
    found: list[str] = []
    for lang, patterns in _LANG_PATTERNS:
        for pat in patterns:
            if re.search(pat, ocr_text, re.MULTILINE | re.IGNORECASE):
                if lang not in found:
                    found.append(lang)
                break
    return found[:5]


def _compute_confidence(
    app_name: str | None,
    ocr_text: str,
    browser_scene: str | None,
    langs: list[str],
    base_scene: str,
) -> float:
    """Heuristic confidence score."""
    score = 0.35
    if app_name:
        score += 0.20
    if ocr_text and len(ocr_text) > 100:
        score += 0.15
    if browser_scene:
        score += 0.15
    if langs:
        score += 0.10
    if base_scene not in ("unknown", "other"):
        score += 0.05
    return round(min(score, 0.95), 2)


def _build_probable_task(
    app_name: str | None,
    scene_type: str,
    browser_scene: str | None,
    activity: str | None,
    langs: list[str],
    window_title: str | None,
) -> str:
    """Generate a natural-language task description."""
    subject = "User"

    # Browser with specific fingerprint
    if browser_scene and activity:
        site_map = {
            "claude-ai":        "Claude",
            "chatgpt":          "ChatGPT",
            "github":           "GitHub",
            "swagger-ui":       "Swagger",
            "arxiv":            "arXiv",
            "stackoverflow":    "Stack Overflow",
            "localhost-3000":   "local frontend",
            "localhost-8010":   "local API",
            "youtube-research": "YouTube",
            "pdf-viewer":       "PDF",
            "docs-site":        "documentation",
            "file-explorer":    "File Explorer",
            "cctv-dashboard":   "EIDOLON CCTV",
        }
        site = site_map.get(browser_scene, browser_scene.replace("-", " "))
        return f"{subject} {activity} on {site}"

    # Editor with language context
    if app_name in ("VSCode", "Cursor", "PyCharm", "WebStorm", "IntelliJ"):
        if scene_type == "debugging":
            lang = langs[0] if langs else ""
            return f"{subject} debugging {lang + ' ' if lang else ''}code in {app_name}"
        if "FastAPI" in langs or "Python" in langs:
            return f"{subject} editing Python backend in {app_name}"
        if "React" in langs or "Next.js" in langs or "TypeScript" in langs:
            return f"{subject} editing frontend in {app_name}"
        if langs:
            return f"{subject} coding {langs[0]} in {app_name}"
        return f"{subject} coding in {app_name}"

    # Terminal-specific
    if app_name in ("Terminal", "PowerShell", "CMD", "Bash", "WSL", "Git Bash"):
        if "Git" in langs:
            return f"{subject} running git commands"
        if "Docker" in langs:
            return f"{subject} running Docker commands"
        return f"{subject} working in terminal"

    # Fallback to scene-based
    task = _PROBABLE_TASKS.get(scene_type, "working on computer")
    if app_name and app_name not in ("Chrome", "Firefox", "Edge", "Brave"):
        return f"{subject} {task} ({app_name})"
    return f"{subject} {task}"


def _build_smart_title(
    app_name: str | None,
    scene_type: str,
    browser_scene: str | None,
    activity: str | None,
    langs: list[str],
) -> str:
    """Short title for memory storage, max ~35 chars."""
    # Browser fingerprint takes precedence
    if browser_scene:
        title_map = {
            "swagger-ui":       "Swagger API Testing",
            "github":           "GitHub Code Review",
            "claude-ai":        "Claude AI Research",
            "chatgpt":          "ChatGPT AI Research",
            "arxiv":            "arXiv Paper Reading",
            "stackoverflow":    "Stack Overflow Debug",
            "localhost-3000":   "Frontend Dev Preview",
            "localhost-8010":   "API Dev Testing",
            "youtube-research": "YouTube Video",
            "pdf-viewer":       "PDF Document Reading",
            "file-explorer":    "File Explorer",
            "cctv-dashboard":   "EIDOLON Dashboard",
            "docs-site":        "Documentation Reading",
            "gemini":           "Gemini AI Research",
        }
        return title_map.get(browser_scene, f"Browser: {activity or 'Research'}")

    # App + scene
    if app_name:
        scene_labels = {
            "debugging":       "Debugging",
            "coding":          "Coding",
            "terminal-work":   "Terminal",
            "ai-chat":         "AI Chat",
            "documentation":   "Docs",
            "api-testing":     "API Testing",
            "communication":   "Communication",
            "design":          "Design",
            "video-watching":  "Video",
        }
        if scene_type == "debugging":
            lang = f" {langs[0]}" if langs else ""
            return f"{app_name}{lang} Debugging"
        if app_name in ("VSCode", "Cursor"):
            if "FastAPI" in langs or ("Python" in langs and "React" not in langs):
                return "VSCode Backend Editing"
            if "React" in langs or "Next.js" in langs or "TypeScript" in langs:
                return "VSCode Frontend Editing"
        label = scene_labels.get(scene_type, "")
        return f"{app_name} {label}".strip() if label else app_name

    # Scene only
    fallback_titles = {
        "debugging":         "Code Debugging",
        "coding":            "Code Editing",
        "terminal-work":     "Terminal Session",
        "browser-research":  "Web Research",
        "ai-chat":           "AI Assistant",
        "documentation":     "Documentation",
        "api-testing":       "API Testing",
        "communication":     "Team Communication",
        "design":            "Design Work",
        "video-watching":    "Video Watching",
    }
    return fallback_titles.get(scene_type, "Screen Capture")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_screenshot_enhanced(
    ocr_text: str,
    app_name: str | None,
    image_path: Path | None = None,
    window_title: str | None = None,
) -> dict:
    """
    Enhanced screenshot analysis returning full intelligence metadata.

    Wraps vision_service.analyze_screenshot and adds:
      confidence, active_tools, probable_task, smart_title.

    Never raises.
    """
    try:
        from app.services.vision_service import analyze_screenshot
        base = analyze_screenshot(ocr_text, app_name, image_path)
    except Exception:
        base = {
            "scene_type":    "unknown",
            "workflow_type": "other",
            "ui_layout":     "unknown",
            "dominant_app":  app_name or "unknown",
            "visual_tags":   [],
        }

    try:
        scene_type    = base.get("scene_type", "unknown")
        workflow_type = base.get("workflow_type", "other")

        browser_scene, activity, browser_tools = _detect_browser_context(ocr_text, window_title)
        langs = _detect_languages(ocr_text) if ocr_text else []

        active_tools = sorted(set(browser_tools + langs))

        # Override scene/workflow for browser fingerprints we recognize
        if browser_scene in ("swagger-ui", "localhost-8010"):
            scene_type    = "api-testing"
            workflow_type = "development"
        elif browser_scene in ("claude-ai", "chatgpt", "gemini", "arxiv"):
            scene_type    = "ai-chat"
            workflow_type = "research"
        elif browser_scene == "github":
            scene_type    = "coding"
            workflow_type = "development"
        elif browser_scene == "cctv-dashboard":
            scene_type    = "surveillance-review"
            workflow_type = "security"

        confidence = _compute_confidence(app_name, ocr_text or "", browser_scene, langs, scene_type)

        probable_task = _build_probable_task(
            app_name, scene_type, browser_scene, activity, langs, window_title
        )
        smart_title = _build_smart_title(app_name, scene_type, browser_scene, activity, langs)

        # Extend visual_tags with languages and browser context
        tags = list(base.get("visual_tags", []))
        for lang in langs[:3]:
            lt = lang.lower().replace(".", "").replace(" ", "-")
            if lt not in tags:
                tags.append(lt)
        if browser_scene and browser_scene not in tags:
            tags.append(browser_scene)

        result = {
            **base,
            "scene_type":    scene_type,
            "workflow_type": workflow_type,
            "visual_tags":   tags[:10],
            "confidence":    confidence,
            "active_tools":  active_tools,
            "probable_task": probable_task,
            "smart_title":   smart_title,
        }
        return result

    except Exception as exc:
        logger.warning("Enhanced vision analysis failed: %s", exc)
        return {
            **base,
            "confidence":    0.30,
            "active_tools":  [],
            "probable_task": f"User working on {app_name or 'computer'}",
            "smart_title":   f"{app_name or 'Screen'} Capture",
        }
