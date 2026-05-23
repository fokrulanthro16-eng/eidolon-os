"""
Agent Service — Phase 12 EIDOLON OS action registry.

All actions are:
  - Local-only (no cloud, no network)
  - Safe (explicit allowlist, no shell injection)
  - Non-destructive (read-mostly; write actions are memory-internal only)
  - Transparent (every action returns a result describing what happened)

Available actions:
    open_app              open a whitelisted application
    open_folder           open a folder in Windows Explorer
    summarize_today       daily activity summary from memory
    search_memories       semantic/keyword search of memory store
    open_latest_pdf       find and open the most recent PDF memory file
    continue_last_session retrieve last session context
    start_screen_watch    start the screen watcher background worker
    stop_screen_watch     stop the screen watcher background worker
"""

import logging
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Windows-safe executable resolution
# ---------------------------------------------------------------------------

def _find_exe(names: list[str], extra_paths: list[str] | None = None) -> str | None:
    """
    Resolve an executable path:
      1. Try shutil.which() for each name (respects PATH + PATHEXT on Windows)
      2. Try each extra_paths entry with os.path.expandvars()
    Returns the first match found, or None.
    """
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    for path in (extra_paths or []):
        expanded = os.path.expandvars(path)
        if os.path.isfile(expanded):
            return expanded
    return None


def _launch(cmd: list[str]) -> None:
    """
    Launch a process safely.
    .cmd/.bat files are not Win32 executables — they need 'cmd /c' on Windows.
    """
    if cmd and cmd[0].lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c"] + cmd
    subprocess.Popen(cmd)


# ---------------------------------------------------------------------------
# Safe app allowlist
# Each entry: find (PATH search names), extra (Windows absolute fallbacks),
#             args (extra argv after the exe), url (use os.startfile instead),
#             label (human name for error messages)
# ---------------------------------------------------------------------------

_SAFE_APPS: dict[str, dict] = {
    "vscode": {
        "find":  ["code"],
        "extra": [
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
            r"C:\Program Files\Microsoft VS Code\Code.exe",
        ],
        "args":  ["."],
        "label": "VS Code",
    },
    "code": {
        "find":  ["code"],
        "extra": [
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
            r"C:\Program Files\Microsoft VS Code\Code.exe",
        ],
        "args":  ["."],
        "label": "VS Code",
    },
    "chrome": {
        "find":  ["chrome", "google-chrome"],
        "extra": [
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "args":  [],
        "label": "Chrome",
    },
    "edge": {
        "find":  ["msedge"],
        "extra": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "args":  [],
        "label": "Microsoft Edge",
    },
    "msedge": {
        "find":  ["msedge"],
        "extra": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "args":  [],
        "label": "Microsoft Edge",
    },
    "explorer": {
        "find":  ["explorer.exe", "explorer"],
        "extra": [r"C:\Windows\explorer.exe"],
        "args":  [],
        "label": "Windows Explorer",
    },
    "powershell": {
        "find":  ["pwsh", "powershell"],
        "extra": [
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            r"C:\Program Files\PowerShell\7\pwsh.exe",
        ],
        "args":  [],
        "label": "PowerShell",
    },
    "terminal": {
        "find":  ["wt"],
        "args":  [],
        "label": "Windows Terminal",
    },
    "notepad": {
        "find":  ["notepad"],
        "extra": [r"C:\Windows\System32\notepad.exe"],
        "args":  [],
        "label": "Notepad",
    },
    # URL-based: opened via os.startfile (Windows ShellExecute — no child process needed)
    "browser": {
        "url":   "http://localhost:3000",
        "label": "EIDOLON Dashboard",
    },
    "eidolon": {
        "url":   "http://localhost:3000",
        "label": "EIDOLON Dashboard",
    },
    "api-docs": {
        "url":   "http://127.0.0.1:8010/docs",
        "label": "API Docs",
    },
    "swagger": {
        "url":   "http://127.0.0.1:8010/docs",
        "label": "API Docs",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt_duration(mins: float) -> str:
    if mins < 60:
        return f"{int(mins)}m"
    h = int(mins // 60)
    m = int(mins % 60)
    return f"{h}h {m}m" if m else f"{h}h"


# ---------------------------------------------------------------------------
# Action implementations
# ---------------------------------------------------------------------------

def _action_open_app(app_name: str) -> dict:
    key = app_name.lower().strip()
    spec = _SAFE_APPS.get(key)
    if spec is None:
        available = ", ".join(sorted(_SAFE_APPS))
        return {
            "success": False,
            "message": f"'{app_name}' is not in the safe app list. Available: {available}",
        }

    label = spec.get("label", app_name)

    # URL-based apps — use Windows ShellExecute (os.startfile is safe for http:// URLs)
    if "url" in spec:
        try:
            os.startfile(spec["url"])
            return {"success": True, "message": f"Opened {label}.", "app": app_name}
        except Exception as exc:
            return {"success": False, "message": f"Could not open {label}: {exc}"}

    # Executable-based apps
    exe = _find_exe(spec.get("find", []), spec.get("extra"))
    if exe is None:
        return {
            "success": False,
            "message": (
                f"Could not find {label} on this machine. "
                "Please ensure it is installed and accessible from your PATH."
            ),
        }

    cmd = [exe] + spec.get("args", [])
    # .cmd/.bat files are script files, not Win32 executables — they need cmd /c
    if exe.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c"] + cmd

    try:
        subprocess.Popen(cmd)
        return {"success": True, "message": f"Opened {label}.", "app": app_name}
    except FileNotFoundError:
        return {
            "success": False,
            "message": f"{label} executable not found at: {exe}. Is it installed?",
        }
    except OSError as exc:
        return {
            "success": False,
            "message": f"Failed to open {label}: {exc.strerror}. Ensure the app is installed and accessible.",
        }
    except Exception as exc:
        return {"success": False, "message": str(exc)}


def _action_open_folder(path: str | None) -> dict:
    # Default to project root (not the cwd which is apps/api)
    if not path or path.strip() in ("", ".", "project", "root"):
        try:
            from app.core.config import ROOT_DIR
            abs_path = str(ROOT_DIR)
        except Exception:
            abs_path = os.path.abspath(".")
    else:
        abs_path = os.path.abspath(path)

    if not os.path.exists(abs_path):
        return {"success": False, "message": f"Path does not exist: {abs_path}"}
    try:
        os.startfile(abs_path)
        return {"success": True, "message": f"Opened folder: {abs_path}", "path": abs_path}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


def _action_summarize_today(hours: float = 24.0) -> dict:
    try:
        from app.services.memory_store import memory_store
        from app.services.workflow_service import get_daily_summary
        memories = memory_store.list()
        summary = get_daily_summary(memories, hours=hours)
        return {"success": True, **summary}
    except Exception as exc:
        logger.warning("summarize_today failed: %s", exc)
        return {"success": False, "message": str(exc)}


def _action_search_memories(query: str, limit: int = 10) -> dict:
    if not query or not query.strip():
        return {"success": False, "message": "Search query cannot be empty."}
    try:
        from app.services.search_service import search_memories
        from app.services.memory_store import memory_store
        results = search_memories(query.strip(), memory_store.list())[:limit]
        items = [
            {
                "id":    r["item"]["id"],
                "title": r["item"]["title"],
                "type":  r["item"]["type"],
                "score": round(r.get("score", 0.0), 3),
                "created_at": r["item"].get("created_at", ""),
            }
            for r in results
        ]
        return {"success": True, "query": query, "count": len(items), "results": items}
    except Exception as exc:
        logger.warning("search_memories failed: %s", exc)
        return {"success": False, "message": str(exc)}


def _action_open_latest_pdf() -> dict:
    try:
        from app.services.memory_store import memory_store
        pdfs = [m for m in memory_store.list() if m.get("type") == "pdf" and m.get("file_path")]
        if not pdfs:
            return {"success": False, "message": "No PDF memories found. Upload a PDF first."}
        pdfs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        latest = pdfs[0]
        fpath = latest["file_path"]
        if not os.path.exists(fpath):
            return {"success": False, "message": f"PDF file not found on disk: {fpath}"}
        os.startfile(fpath)
        return {
            "success": True,
            "message": f"Opened: {latest.get('title', 'PDF')}",
            "file_path": fpath,
            "title": latest.get("title", ""),
        }
    except Exception as exc:
        return {"success": False, "message": str(exc)}


def _action_continue_last_session() -> dict:
    try:
        from app.services.session_store import session_store
        sessions = session_store.get_sessions()
        if not sessions:
            return {"success": False, "message": "No sessions found. Start the screen watcher to create sessions."}
        sessions.sort(key=lambda s: s.get("start_time", ""), reverse=True)
        last = sessions[0]
        return {
            "success": True,
            "session_id":    last.get("id"),
            "label":         last.get("label", "Unnamed session"),
            "start_time":    last.get("start_time"),
            "end_time":      last.get("end_time"),
            "memory_count":  last.get("memory_count", 0),
            "duration_str":  last.get("duration_str", ""),
            "dominant_app":  last.get("dominant_app", ""),
            "message":       f"Last session: {last.get('label', '')} — {last.get('duration_str', '')}",
        }
    except Exception as exc:
        return {"success": False, "message": str(exc)}


def _action_start_screen_watch(interval_seconds: int = 30) -> dict:
    try:
        from app.workers.screen_watcher import is_running, run_screen_watcher
        if is_running():
            return {"success": True, "message": "Screen watcher is already running.", "running": True}
        started = run_screen_watcher(interval_seconds)
        return {
            "success": started,
            "running": started,
            "message": f"Screen watcher started (interval={interval_seconds}s)." if started else "Failed to start screen watcher.",
        }
    except Exception as exc:
        return {"success": False, "message": str(exc)}


def _action_stop_screen_watch() -> dict:
    try:
        from app.workers.screen_watcher import is_running, stop_screen_watcher
        if not is_running():
            return {"success": True, "message": "Screen watcher was not running.", "running": False}
        stopped = stop_screen_watcher()
        return {
            "success": stopped,
            "running": False,
            "message": "Screen watcher stopped." if stopped else "Could not stop screen watcher.",
        }
    except Exception as exc:
        return {"success": False, "message": str(exc)}


# ---------------------------------------------------------------------------
# Action registry
# ---------------------------------------------------------------------------

ACTIONS: dict[str, dict] = {
    "open_app": {
        "name":        "open_app",
        "label":       "Open Application",
        "description": "Open a whitelisted application (VSCode, Terminal, Browser, Explorer…)",
        "args":        {"app_name": "string — app to open (e.g. 'vscode', 'terminal', 'explorer')"},
        "icon":        "⬡",
    },
    "open_folder": {
        "name":        "open_folder",
        "label":       "Open Project Folder",
        "description": "Open the EIDOLON project root folder in Windows Explorer.",
        "args":        {"path": "string — folder path (default: project root)"},
        "icon":        "◫",
    },
    "summarize_today": {
        "name":        "summarize_today",
        "label":       "Summarize Today",
        "description": "Generate a daily activity summary from memory.",
        "args":        {"hours": "float — lookback window in hours (default: 24)"},
        "icon":        "◈",
    },
    "search_memories": {
        "name":        "search_memories",
        "label":       "Search Memories",
        "description": "Search memories by keyword or semantic query.",
        "args":        {"query": "string — search query", "limit": "int — max results (default: 10)"},
        "icon":        "⬡",
    },
    "open_latest_pdf": {
        "name":        "open_latest_pdf",
        "label":       "Open Latest PDF",
        "description": "Find and open the most recently ingested PDF file.",
        "args":        {},
        "icon":        "◉",
    },
    "continue_last_session": {
        "name":        "continue_last_session",
        "label":       "Continue Last Session",
        "description": "Retrieve context from the last detected work session.",
        "args":        {},
        "icon":        "◎",
    },
    "start_screen_watch": {
        "name":        "start_screen_watch",
        "label":       "Start Screen Watch",
        "description": "Start the background screen capture and memory worker.",
        "args":        {"interval_seconds": "int — capture interval in seconds (default: 30)"},
        "icon":        "⬡",
    },
    "stop_screen_watch": {
        "name":        "stop_screen_watch",
        "label":       "Stop Screen Watch",
        "description": "Stop the background screen capture worker.",
        "args":        {},
        "icon":        "⬡",
    },
}


def list_actions() -> list[dict]:
    return list(ACTIONS.values())


def get_screen_watch_status() -> bool:
    try:
        from app.workers.screen_watcher import is_running
        return is_running()
    except Exception:
        return False


def execute_action(action: str, args: dict[str, Any] | None = None) -> dict:
    """
    Execute a named agent action.

    Returns a result dict always containing:
      success: bool
      message: str
      (plus action-specific keys)
    """
    args = args or {}

    dispatch = {
        "open_app":               lambda: _action_open_app(str(args.get("app_name", ""))),
        "open_folder":            lambda: _action_open_folder(args.get("path")),
        "summarize_today":        lambda: _action_summarize_today(float(args.get("hours", 24))),
        "search_memories":        lambda: _action_search_memories(str(args.get("query", "")), int(args.get("limit", 10))),
        "open_latest_pdf":        lambda: _action_open_latest_pdf(),
        "continue_last_session":  lambda: _action_continue_last_session(),
        "start_screen_watch":     lambda: _action_start_screen_watch(int(args.get("interval_seconds", 30))),
        "stop_screen_watch":      lambda: _action_stop_screen_watch(),
    }

    if action not in dispatch:
        return {
            "success": False,
            "message": f"Unknown action '{action}'. Available: {', '.join(sorted(dispatch))}",
        }

    logger.info("agent.execute: action=%s  args=%s", action, args)
    try:
        return dispatch[action]()
    except Exception as exc:
        logger.warning("agent.execute error: %s", exc)
        return {"success": False, "message": str(exc)}
