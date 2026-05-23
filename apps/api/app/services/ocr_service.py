"""
OCR service — extracts text from images using Tesseract via pytesseract.

Resolution order for the Tesseract binary:
    1. TESSERACT_CMD env var (override for custom installs)
    2. C:\\Program Files\\Tesseract-OCR\\tesseract.exe  (standard Windows path)
    3. Assume 'tesseract' is on PATH (Linux / macOS / custom Windows)

All errors degrade gracefully — the pipeline never crashes on OCR failure.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tesseract binary resolution (runs once at import time)
# ---------------------------------------------------------------------------

_WINDOWS_DEFAULT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_TESSERACT_CMD: str | None = None


def _resolve_tesseract() -> str | None:
    """Return the tesseract command to use, or None if not found."""
    # 1. Explicit env override
    env = os.environ.get("TESSERACT_CMD", "").strip()
    if env and Path(env).is_file():
        return env

    # 2. Standard Windows install path
    if Path(_WINDOWS_DEFAULT).is_file():
        return _WINDOWS_DEFAULT

    # 3. Assume it's on PATH — let pytesseract use its own default
    return None


_TESSERACT_CMD = _resolve_tesseract()

if _TESSERACT_CMD:
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = _TESSERACT_CMD
        logger.info("Tesseract configured: %s", _TESSERACT_CMD)
    except ImportError:
        pass  # pytesseract not installed — handled at call site

# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

_MAX_OCR_CHARS = 4000

# Matches runs of 3+ identical non-alphanumeric/non-space characters (noise like |||, ----, ###)
_NOISE_RUN_RE = re.compile(r"([^\w\s])\1{2,}")

# Detects URL-like tokens — preserve these verbatim
_URL_RE = re.compile(r"https?://\S+|www\.\S+")

# Detects code-like tokens (camelCase, snake_case, dot.separated) — preserve
_CODE_TOKEN_RE = re.compile(r"\w+[._]\w+|\w+[A-Z]\w*")


def _clean(raw: str) -> str:
    """
    Normalise raw Tesseract output:
        - Strip non-printable characters (keep printable ASCII + tab + newline)
        - Remove runs of 3+ identical non-alphanumeric chars (noise symbols)
        - Collapse whitespace runs within lines
        - Drop blank lines
        - Preserve URLs and code-like tokens
        - Cap output at _MAX_OCR_CHARS characters
    """
    lines = []
    for line in raw.splitlines():
        # Remove non-printable characters (keep tab and printable ASCII 32–126)
        line = "".join(ch for ch in line if ch == "\t" or (32 <= ord(ch) <= 126))
        # Remove noise symbol runs (e.g. |||, ---, ###)
        line = _NOISE_RUN_RE.sub(" ", line)
        # Collapse whitespace
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    result = "\n".join(lines)
    if len(result) > _MAX_OCR_CHARS:
        result = result[:_MAX_OCR_CHARS]
    return result


# ---------------------------------------------------------------------------
# Image preprocessing (improves OCR on UI screenshots)
# ---------------------------------------------------------------------------

def _preprocess(img: Any) -> Any:
    """
    Multi-stage preprocessing optimised for UI screenshots:
        1. Grayscale conversion
        2. Autocontrast (histogram stretch, removes extreme noise)
        3. Unsharp mask (sharpens text edges without adding noise)
        4. Optional: simple binarisation threshold for high-contrast screens

    All stages are wrapped in individual try/except blocks so a failure in
    any stage gracefully degrades to the output of the previous stage.
    Returns at minimum a grayscale image, never crashes.
    """
    # Stage 1 — grayscale (mandatory base)
    try:
        gray = img.convert("L")
    except Exception:
        return img

    # Stage 2 — autocontrast (stretches histogram; cutoff=1 clips 1% each end)
    try:
        from PIL import ImageOps
        gray = ImageOps.autocontrast(gray, cutoff=1)
    except Exception:
        pass  # keep gray as-is

    # Stage 3 — unsharp mask (sharpens text without amplifying uniform noise)
    try:
        from PIL import ImageFilter
        gray = gray.filter(ImageFilter.UnsharpMask(radius=1, percent=180, threshold=3))
    except Exception:
        pass

    # Stage 4 — adaptive-style binarisation via PIL only (no cv2)
    # Blur a copy to get local mean, then threshold each pixel against it.
    # Only applied when the image is large enough that local context matters.
    try:
        if gray.width >= 400 and gray.height >= 200:
            from PIL import ImageFilter, ImageChops
            blurred   = gray.filter(ImageFilter.GaussianBlur(radius=15))
            # pixel > (local_mean + 8) → white; else → black
            diff      = ImageChops.subtract(gray, blurred)
            threshold = diff.point(lambda p: 255 if p > 8 else 0)
            gray = threshold
    except Exception:
        pass  # keep the sharpened gray

    return gray


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_FALLBACK_TEXT = (
    "[OCR unavailable] Image stored successfully. "
    "OCR engine is not configured yet."
)


def extract_text_from_image(image_path: Path) -> dict[str, Any]:
    """
    Extract text from an image file.

    Returns a dict with:
        text        str   — cleaned OCR output, or fallback message
        engine      str   — "tesseract" | "fallback"
        available   bool  — True when real OCR ran
        confidence  float — average word-level confidence (0-100), or -1
    """
    try:
        import pytesseract
        from PIL import Image

        # Re-apply cmd in case the service was imported before pytesseract was installed
        if _TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = _TESSERACT_CMD

        with Image.open(image_path) as img:
            processed = _preprocess(img)

            # image_to_data gives per-word confidence scores
            data = pytesseract.image_to_data(
                processed,
                lang="eng",
                output_type=pytesseract.Output.DICT,
            )

        # Build cleaned text from words with confidence >= 0
        words = [
            w
            for w, c in zip(data["text"], data["conf"])
            if isinstance(c, (int, float)) and c >= 0 and str(w).strip()
        ]
        raw_text = " ".join(words)
        text = _clean(raw_text)

        # Average confidence over words Tesseract actually recognised
        valid_confs = [
            float(c)
            for c in data["conf"]
            if isinstance(c, (int, float)) and c >= 0
        ]
        confidence = round(sum(valid_confs) / len(valid_confs), 1) if valid_confs else -1.0

        if text:
            return {
                "text": text,
                "engine": "tesseract",
                "available": True,
                "confidence": confidence,
            }

        return {
            "text": "[OCR ran but found no readable text in this image]",
            "engine": "tesseract",
            "available": True,
            "confidence": confidence,
        }

    except ImportError:
        logger.debug("pytesseract not installed — using fallback")
    except pytesseract.TesseractNotFoundError:  # type: ignore[attr-defined]
        logger.warning(
            "Tesseract executable not found. "
            "Install from https://github.com/UB-Mannheim/tesseract/wiki "
            "or set TESSERACT_CMD env var."
        )
    except Exception as exc:
        logger.warning("OCR failed for %s: %s", image_path.name, exc)

    return {
        "text": _FALLBACK_TEXT,
        "engine": "fallback",
        "available": False,
        "confidence": -1.0,
    }
