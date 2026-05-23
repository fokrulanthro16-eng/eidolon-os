import logging
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import SCREENSHOTS_DIR

logger = logging.getLogger(__name__)


def capture_screen() -> Path:
    """
    Capture the full screen and save as PNG.

    Tries in order:
        1. mss  — fastest, zero GUI side-effects (install: pip install mss)
        2. PIL.ImageGrab — built into Pillow, works on Windows with no extras

    Returns the absolute Path to the saved file.
    """
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    dest = SCREENSHOTS_DIR / f"screen_{ts}.png"

    try:
        import mss
        import mss.tools

        with mss.mss() as sct:
            # monitors[0] is the virtual screen spanning all monitors
            monitor = sct.monitors[0]
            frame = sct.grab(monitor)
            mss.tools.to_png(frame.rgb, frame.size, output=str(dest))

        logger.debug("Screenshot saved via mss: %s", dest.name)
        return dest

    except ImportError:
        pass  # mss not installed — fall through to ImageGrab
    except Exception as exc:
        logger.warning("mss capture failed (%s), falling back to ImageGrab", exc)

    # Pillow ImageGrab — always available on Windows when Pillow is installed
    from PIL import ImageGrab

    img = ImageGrab.grab()
    img.save(str(dest), format="PNG")
    logger.debug("Screenshot saved via ImageGrab: %s", dest.name)
    return dest
