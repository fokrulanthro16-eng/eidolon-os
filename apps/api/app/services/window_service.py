"""
Active window detection using only ctypes (stdlib).
No pywin32, no psutil — zero extra dependencies.

Returns the foreground window's title and process (exe) name.
Normalises common exe names to friendly labels (VSCode, Chrome, etc.).
"""

import ctypes
import ctypes.wintypes
import logging
import os
import platform

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Friendly name mapping  (exe.lower() → display label)
# ---------------------------------------------------------------------------

_APP_LABELS: dict[str, str] = {
    "code.exe":                "VSCode",
    "code - insiders.exe":     "VSCode",
    "cursor.exe":              "Cursor",
    "pycharm64.exe":           "PyCharm",
    "pycharm.exe":             "PyCharm",
    "idea64.exe":              "IntelliJ",
    "webstorm64.exe":          "WebStorm",
    "devenv.exe":              "VS",
    "chrome.exe":              "Chrome",
    "firefox.exe":             "Firefox",
    "msedge.exe":              "Edge",
    "brave.exe":               "Brave",
    "opera.exe":               "Opera",
    "arc.exe":                 "Arc",
    "windowsterminal.exe":     "Terminal",
    "wt.exe":                  "Terminal",
    "cmd.exe":                 "CMD",
    "powershell.exe":          "PowerShell",
    "pwsh.exe":                "PowerShell",
    "wsl.exe":                 "WSL",
    "bash.exe":                "Bash",
    "git-bash.exe":            "Git Bash",
    "notepad.exe":             "Notepad",
    "notepad++.exe":           "Notepad++",
    "obsidian.exe":            "Obsidian",
    "notion.exe":              "Notion",
    "winword.exe":             "Word",
    "excel.exe":               "Excel",
    "powerpnt.exe":            "PowerPoint",
    "outlook.exe":             "Outlook",
    "teams.exe":               "Teams",
    "slack.exe":               "Slack",
    "discord.exe":             "Discord",
    "zoom.exe":                "Zoom",
    "postman.exe":             "Postman",
    "insomnia.exe":            "Insomnia",
    "dbeaver.exe":             "DBeaver",
    "datagrip64.exe":          "DataGrip",
    "figma.exe":               "Figma",
    "gimp-2.10.exe":           "GIMP",
    "photoshop.exe":           "Photoshop",
    "spotify.exe":             "Spotify",
    "vlc.exe":                 "VLC",
    "explorer.exe":            "Explorer",
}

# ---------------------------------------------------------------------------
# Ignored processes (system chrome / idle apps that add no useful context)
# ---------------------------------------------------------------------------

_IGNORE: frozenset[str] = frozenset({
    "dwm.exe",
    "searchhost.exe",
    "searchindexer.exe",
    "taskhostw.exe",
    "svchost.exe",
    "rundll32.exe",
    "applicationframehost.exe",
    "systemsettings.exe",
    "lockapp.exe",
    "logonui.exe",
})


# ---------------------------------------------------------------------------
# Internal ctypes helpers
# ---------------------------------------------------------------------------

def _get_process_name(pid: int) -> str | None:
    """Return the executable filename for a PID using only kernel32."""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    try:
        h = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not h:
            return None
        buf = ctypes.create_unicode_buffer(1024)
        size = ctypes.wintypes.DWORD(1024)
        ok = ctypes.windll.kernel32.QueryFullProcessImageNameW(
            h, 0, buf, ctypes.byref(size)
        )
        ctypes.windll.kernel32.CloseHandle(h)
        if ok:
            return os.path.basename(buf.value)
    except Exception:
        pass
    return None


def _friendly_fallback(exe: str) -> str:
    """Strip .exe and title-case: 'myprog.exe' → 'Myprog'."""
    name = os.path.splitext(exe)[0]
    return name.title() if name else exe


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_active_window_info() -> dict[str, str | None]:
    """
    Capture the foreground window title and process name.

    Returns:
        {
            "window_title": str | None,  — full window title bar text
            "app_name":     str | None,  — friendly label e.g. "VSCode"
            "exe_name":     str | None,  — raw filename e.g. "code.exe"
        }

    Never raises — returns all-None on any failure (non-Windows, permissions, etc.).
    """
    result: dict[str, str | None] = {
        "window_title": None,
        "app_name": None,
        "exe_name": None,
    }

    if platform.system() != "Windows":
        return result

    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return result

        # Window title
        title_buf = ctypes.create_unicode_buffer(512)
        ctypes.windll.user32.GetWindowTextW(hwnd, title_buf, 512)
        window_title = title_buf.value.strip() or None

        # Process ID
        pid = ctypes.wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        exe_name = _get_process_name(pid.value)
        if not exe_name:
            return result

        exe_lower = exe_name.lower()
        if exe_lower in _IGNORE:
            return result

        app_name = _APP_LABELS.get(exe_lower) or _friendly_fallback(exe_name)

        result["window_title"] = window_title
        result["app_name"] = app_name
        result["exe_name"] = exe_name

    except Exception as exc:
        logger.debug("window detection skipped: %s", exc)

    return result
