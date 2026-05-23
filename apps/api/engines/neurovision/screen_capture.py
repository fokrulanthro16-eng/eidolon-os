"""
NeuroVision — Screen capture engine.
Uses mss for fast, low-overhead screen grabbing (no GDI+ overhead).
Supports primary monitor, specific monitor, or full virtual screen.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class CaptureFrame:
    image: Image.Image
    captured_at: datetime
    source_app: str | None
    window_title: str | None
    monitor_index: int


def capture_screen(max_width: int = 1920, monitor_index: int = 1) -> CaptureFrame:
    """
    Capture specified monitor. monitor_index=0 is the virtual combined screen.
    monitor_index=1 is the primary monitor (default).
    """
    import mss

    with mss.mss() as sct:
        monitors = sct.monitors
        if monitor_index >= len(monitors):
            monitor_index = 1
        monitor = monitors[monitor_index]
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)

    from apps.api.engines.neurovision.window_tracker import get_active_window_info
    source_app, window_title = get_active_window_info()

    return CaptureFrame(
        image=img,
        captured_at=datetime.now(timezone.utc),
        source_app=source_app,
        window_title=window_title,
        monitor_index=monitor_index,
    )


def save_screenshot(image: Image.Image, save_dir: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:19]
    path = save_dir / f"cap_{ts}.webp"
    image.save(path, "WEBP", quality=85)
    return path
