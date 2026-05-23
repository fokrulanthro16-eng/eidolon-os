"""
Vision intelligence service — lightweight heuristic scene analysis for screenshots.

Pipeline (< 50 ms per frame, no GPU, no OpenCV):
  1. App-name lookup      O(1) dict
  2. OCR text patterns    regex on ~4 000 chars
  3. PIL thumbnail colors  80×60 resize

Output schema
-------------
scene_type    str   — "coding" | "debugging" | "terminal-work" | "browser-research" |
                       "ai-chat" | "documentation" | "communication" | "design" |
                       "video-watching" | "unknown"
workflow_type str   — "development" | "research" | "communication" | "creative" |
                       "learning" | "other"
ui_layout     str   — "dark-editor" | "light-browser" | "split-view" |
                       "terminal-only" | "unknown"
dominant_app  str   — resolved app name or "unknown"
visual_tags   list  — up to 8 tags, e.g. ["coding", "dark-theme", "editor"]
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static lookup tables
# ---------------------------------------------------------------------------

_APP_SCENE: dict[str, str] = {
    "VSCode":          "coding",
    "Cursor":          "coding",
    "PyCharm":         "coding",
    "IntelliJ":        "coding",
    "WebStorm":        "coding",
    "Eclipse":         "coding",
    "Android Studio":  "coding",
    "Xcode":           "coding",
    "Vim":             "coding",
    "Neovim":          "coding",
    "Terminal":        "terminal-work",
    "PowerShell":      "terminal-work",
    "CMD":             "terminal-work",
    "iTerm":           "terminal-work",
    "Hyper":           "terminal-work",
    "Chrome":          "browser-research",
    "Firefox":         "browser-research",
    "Edge":            "browser-research",
    "Brave":           "browser-research",
    "Safari":          "browser-research",
    "Slack":           "communication",
    "Discord":         "communication",
    "Teams":           "communication",
    "Notion":          "documentation",
    "Obsidian":        "documentation",
    "Word":            "documentation",
    "Figma":           "design",
    "Postman":         "api-testing",
    "Insomnia":        "api-testing",
    "Spotify":         "entertainment",
    "VLC":             "entertainment",
}

_APP_WORKFLOW: dict[str, str] = {
    "coding":           "development",
    "debugging":        "development",
    "terminal-work":    "development",
    "api-testing":      "development",
    "browser-research": "research",
    "ai-chat":          "research",
    "documentation":    "research",
    "video-watching":   "learning",
    "communication":    "communication",
    "design":           "creative",
    "entertainment":    "other",
    "unknown":          "other",
}

# OCR patterns → scene type  (first match wins within a tier; debugging/ai-chat always dominate)
_SCENE_PATTERNS: list[tuple[str, list[str]]] = [
    ("debugging", [
        r"\bTraceback\b", r"\bException\b.*line \d+", r"\bError\b.*line \d+",
        r"\bbreakpoint\b", r"\bstack trace\b", r"\bSegmentation fault\b",
        r"\bTypeError\b", r"\bNameError\b", r"\bAttributeError\b",
        r"\bSyntaxError\b", r"\bIndexError\b", r"\bKeyError\b",
    ]),
    ("ai-chat", [
        r"\bClaude\b", r"\bChatGPT\b", r"\bGPT-4\b", r"\bCopilot\b",
        r"Human\s*:\s", r"Assistant\s*:\s", r"Gemini\b",
        r"\bAnthropic\b",
    ]),
    ("coding", [
        r"\bdef \w+\s*\(", r"\bclass \w+\s*[:(]",
        r"^from \w+ import", r"^import \w",
        r"\bfunction\s+\w+\s*\(", r"\bconst \w+\s*=",
        r"\bpublic \w+ \w+\s*\(", r"#include\s*<",
        r"\bpackage \w+\b", r"\bfn \w+\s*\(",
    ]),
    ("terminal-work", [
        r"^\$\s+\w", r"^C:\\[^>]*>", r"^>>>\s",
        r"\bnpm\s+(install|run|start|build)\b",
        r"\bpip\s+(install|list|show|freeze)\b",
        r"\bgit\s+(add|commit|push|pull|clone|status)\b",
        r"\bpython\b.*\.py\b", r"\bdocker\s+\w+\b",
        r"\bkubectl\b",
    ]),
    ("browser-research", [
        r"https?://\S+", r"\bstackoverflow\.com\b", r"\bgithub\.com\b",
        r"\bwikipedia\.org\b", r"\bdocs\.\w+\.\w+\b",
        r"\bGoogle Search\b", r"\bSearch results?\b",
        r"\bNew Tab\b",
    ]),
    ("documentation", [
        r"^#{1,3}\s+\w", r"\bREADME\b", r"\bAPI reference\b",
        r"\bParameters\b.*:", r"\bReturns\b.*:", r"\bExample usage\b",
        r"\bTable of Contents\b",
    ]),
    ("video-watching", [
        r"\bYouTube\b", r"\byoutu\.be\b", r"\bNetflix\b",
        r"\bTwitch\b", r"\bPrime Video\b",
    ]),
    ("communication", [
        r"\bSend a message\b", r"\bType a message\b",
        r"\bReply in thread\b", r"\bUnread messages\b",
        r"\bDirect Messages\b",
    ]),
    ("design", [
        r"\bLayers\b.*panel", r"\bArtboard\b", r"\bFill\b.*Stroke\b",
        r"\bOpacity\s*:\s*\d+", r"\bGroup\b.*\bFrame\b",
        r"\bVector\b.*edit",
    ]),
]

# UI structure hints from OCR
_UI_ELEMENTS: dict[str, list[str]] = {
    "editor":   [r"Ln \d+,?\s*Col \d+", r"\bUTF-8\b", r"\bCRLF\b|\bLF\b",
                 r"line \d+.*col(?:umn)? \d+"],
    "terminal": [r"^\$\s", r"^>>>\s", r"C:\\[^>]*>"],
    "browser":  [r"https?://", r"\bNew Tab\b", r"\bchrome://\b", r"\bBack\b.*\bForward\b"],
    "sidebar":  [r"\bEXPLORER\b", r"\bOUTLINE\b", r"\bSOURCE CONTROL\b",
                 r"\bEXTENSIONS\b", r"\bSEARCH\b"],
    "menu-bar": [r"File\s+Edit\s+View", r"File\s+Edit\s+\w+\s+Help"],
}

# App combo → workflow description (for session-level analysis)
WORKFLOW_COMBOS: dict[frozenset, str] = {
    frozenset({"VSCode",   "Chrome"}):    "coding + research",
    frozenset({"VSCode",   "Terminal"}):  "active development",
    frozenset({"Cursor",   "Chrome"}):    "AI-assisted development",
    frozenset({"PyCharm",  "Chrome"}):    "Python development",
    frozenset({"VSCode",   "Postman"}):   "API development",
    frozenset({"Chrome",   "Slack"}):     "remote collaboration",
    frozenset({"VSCode",   "Slack"}):     "remote development",
    frozenset({"Figma",    "VSCode"}):    "design + implementation",
    frozenset({"Obsidian", "Chrome"}):    "research + notes",
}


# ---------------------------------------------------------------------------
# Image colour analysis (PIL only — no OpenCV)
# ---------------------------------------------------------------------------

def _analyse_colors(path: Path) -> dict:
    """Return brightness statistics from an 80×60 thumbnail. Non-fatal."""
    try:
        from PIL import Image, ImageStat
        with Image.open(path) as img:
            thumb      = img.convert("RGB").resize((80, 60))
            stat       = ImageStat.Stat(thumb)
            brightness = sum(stat.mean[:3]) / 3
            variance   = sum(stat.stddev[:3]) / 3

            left_stat  = ImageStat.Stat(thumb.crop((0, 0, 8, 60)))
            left_b     = sum(left_stat.mean[:3]) / 3

            return {
                "brightness":       round(brightness, 1),
                "is_dark":          brightness < 100,
                "color_variance":   round(variance, 1),
                "has_dark_sidebar": left_b < 60 and brightness > left_b + 25,
            }
    except Exception as exc:
        logger.debug("Colour analysis failed: %s", exc)
        return {"brightness": -1, "is_dark": None, "color_variance": 0, "has_dark_sidebar": False}


# ---------------------------------------------------------------------------
# Pattern helpers
# ---------------------------------------------------------------------------

def _match_scene(ocr_text: str) -> str | None:
    for scene_type, patterns in _SCENE_PATTERNS:
        for pat in patterns:
            if re.search(pat, ocr_text, re.MULTILINE | re.IGNORECASE):
                return scene_type
    return None


def _detect_ui_elements(ocr_text: str) -> list[str]:
    found = []
    for element, patterns in _UI_ELEMENTS.items():
        for pat in patterns:
            if re.search(pat, ocr_text, re.MULTILINE | re.IGNORECASE):
                found.append(element)
                break
    return found


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_screenshot(
    ocr_text: str,
    app_name: str | None,
    image_path: Path | None = None,
) -> dict:
    """
    Analyse a screenshot and return structured scene metadata.

    Parameters
    ----------
    ocr_text    : extracted text (may be empty)
    app_name    : active app name from window detection (may be None)
    image_path  : path to the image file for colour analysis (optional)

    Returns
    -------
    dict with scene_type, workflow_type, ui_layout, dominant_app, visual_tags
    Never raises.
    """
    try:
        app_scene = _APP_SCENE.get(app_name or "", None)
        dominant  = app_name or "unknown"
        ocr_scene = _match_scene(ocr_text) if ocr_text else None

        # Resolve scene: high-priority OCR signals override app-based guesses
        if ocr_scene in ("debugging", "ai-chat"):
            scene_type = ocr_scene
        elif app_scene:
            if app_scene == "browser-research" and ocr_scene in (
                "ai-chat", "documentation", "video-watching", "communication"
            ):
                scene_type = ocr_scene
            else:
                scene_type = app_scene
        elif ocr_scene:
            scene_type = ocr_scene
        else:
            scene_type = "unknown"

        workflow_type = _APP_WORKFLOW.get(scene_type, "other")
        ui_elements   = _detect_ui_elements(ocr_text) if ocr_text else []
        color_info    = _analyse_colors(image_path) if image_path else {}
        is_dark       = color_info.get("is_dark")

        # ui_layout
        if scene_type == "terminal-work" or ui_elements == ["terminal"]:
            ui_layout = "terminal-only"
        elif "editor" in ui_elements and (is_dark or color_info.get("has_dark_sidebar")):
            ui_layout = "dark-editor"
        elif is_dark is True:
            ui_layout = "dark-editor"
        elif is_dark is False:
            ui_layout = "light-browser"
        elif "editor" in ui_elements and "browser" in ui_elements:
            ui_layout = "split-view"
        else:
            ui_layout = "unknown"

        # visual_tags (ordered: scene > workflow > theme > UI elements > app)
        raw_tags: list[str] = []
        if scene_type != "unknown":
            raw_tags.append(scene_type)
        if workflow_type != "other":
            raw_tags.append(workflow_type)
        if is_dark is True:
            raw_tags.append("dark-theme")
        elif is_dark is False:
            raw_tags.append("light-theme")
        raw_tags.extend(ui_elements)
        if app_name:
            raw_tags.append(app_name.lower().replace(" ", "-"))

        seen: set[str] = set()
        visual_tags: list[str] = []
        for t in raw_tags:
            if t not in seen:
                seen.add(t)
                visual_tags.append(t)

        return {
            "scene_type":    scene_type,
            "workflow_type": workflow_type,
            "ui_layout":     ui_layout,
            "dominant_app":  dominant,
            "visual_tags":   visual_tags[:8],
        }

    except Exception as exc:
        logger.warning("Vision analysis failed: %s", exc)
        return {
            "scene_type":    "unknown",
            "workflow_type": "other",
            "ui_layout":     "unknown",
            "dominant_app":  app_name or "unknown",
            "visual_tags":   [],
        }


def analyze_workflow_context(app_names: list[str]) -> str:
    """
    Given app names observed in a session, return a workflow description string.
    Used by session & profile services.
    """
    app_set = frozenset(app_names)
    for combo, description in WORKFLOW_COMBOS.items():
        if combo <= app_set:
            return description
    # Majority-vote fallback
    workflows = [
        _APP_WORKFLOW.get(_APP_SCENE.get(a, "unknown"), "other")
        for a in app_names
    ]
    if workflows:
        from collections import Counter
        return Counter(workflows).most_common(1)[0][0]
    return "other"
