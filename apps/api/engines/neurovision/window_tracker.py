"""
Windows active window metadata extractor.
Returns (process_name, window_title) for context-aware memory tagging.
Gracefully returns (None, None) on non-Windows or permission errors.
"""
import logging

logger = logging.getLogger(__name__)

_IGNORED_PROCESSES = {"dwm.exe", "explorer.exe", "SearchHost.exe"}


def get_active_window_info() -> tuple[str | None, str | None]:
    try:
        import win32gui
        import win32process
        import psutil

        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return None, None

        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            proc_name = None

        if proc_name and proc_name in _IGNORED_PROCESSES:
            return None, title  # still return title, skip process name

        return proc_name, title

    except ImportError:
        # pywin32 not installed — running in non-Windows dev environment
        return None, None
    except Exception as e:
        logger.debug("Active window detection failed: %s", e)
        return None, None
