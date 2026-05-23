"""
PDF text-extraction service.

Resolution order
----------------
1. PyMuPDF (fitz)  — best quality, handles text-layer PDFs and returns page count.
2. Graceful fallback — API remains fully functional; PDF is stored but not searchable
   until PyMuPDF is installed.

Scanned PDF architecture
------------------------
Pages with no extractable text (< 20 chars) are flagged as scanned.
The architecture is primed for a Tesseract OCR fallback: render the page as
a PIL Image and pass it through ocr_service.extract_text_from_image().
That second-tier pipeline is wired in but guarded by Tesseract availability,
so the API never crashes and the feature degrades gracefully.

Constants
---------
_MAX_CHARS_PER_PAGE  : per-page text cap (avoids huge pages dominating the embedding)
_MAX_TOTAL_CHARS     : total text cap stored in the memory item (~15 k chars)
_MAX_PAGES_EXTRACT   : never process more than this many pages
"""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MAX_CHARS_PER_PAGE = 2_000
_MAX_TOTAL_CHARS    = 15_000
_MAX_PAGES_EXTRACT  = 50
_SCANNED_THRESHOLD  = 20  # chars — below this the page is treated as scanned


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_page_text(raw: str) -> str:
    """Normalise a page's raw text: collapse blanks, drop empty lines."""
    lines = []
    for line in raw.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _is_scanned(raw: str) -> bool:
    return len(raw.strip()) < _SCANNED_THRESHOLD


def _ocr_page_image(page) -> str:
    """
    Render a scanned page to a PIL Image and run Tesseract if available.
    Returns the extracted text or an informational placeholder.
    """
    try:
        # Render page at 2× scale for better OCR accuracy (150 dpi effective)
        mat  = page.get_transformation_matrix(2.0, 2.0)  # fitz.Matrix(2, 2)
        pix  = page.get_pixmap(matrix=mat, colorspace="gray")
        img_bytes = pix.tobytes("png")

        from io import BytesIO
        from PIL import Image
        from app.services.ocr_service import extract_text_from_image

        # Write to a temp-in-memory path wrapper that ocr_service accepts
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(img_bytes)
            tmp_path = Path(tmp.name)
        try:
            result = extract_text_from_image(tmp_path)
            return result.get("text", "") if result.get("available") else ""
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    except Exception as exc:
        logger.debug("Scanned-page OCR failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# PyMuPDF extraction
# ---------------------------------------------------------------------------

def _extract_with_pymupdf(path: Path) -> dict[str, Any]:
    import fitz  # PyMuPDF

    doc          = fitz.open(str(path))
    page_count   = len(doc)
    scanned      = 0
    pages_text: list[str] = []

    for i in range(min(page_count, _MAX_PAGES_EXTRACT)):
        page    = doc[i]
        raw     = page.get_text("text")
        label   = f"[Page {i + 1}]"

        if _is_scanned(raw):
            scanned += 1
            # Attempt OCR on the rendered page image (Tesseract, if installed)
            ocr_text = _ocr_page_image(page)
            if ocr_text:
                cleaned = _clean_page_text(ocr_text)
                pages_text.append(f"{label}\n{cleaned[:_MAX_CHARS_PER_PAGE]}")
            else:
                pages_text.append(f"{label} [scanned image — install Tesseract for OCR]")
        else:
            cleaned = _clean_page_text(raw)
            if len(cleaned) > _MAX_CHARS_PER_PAGE:
                cleaned = cleaned[:_MAX_CHARS_PER_PAGE] + "…"
            pages_text.append(f"{label}\n{cleaned}" if cleaned else f"{label} [empty]")

    doc.close()

    full_text = "\n\n".join(pages_text)
    if len(full_text) > _MAX_TOTAL_CHARS:
        full_text = full_text[:_MAX_TOTAL_CHARS] + "\n\n[… text truncated at 15 000 chars]"

    return {
        "text":                 full_text,
        "page_count":           page_count,
        "pages_extracted":      min(page_count, _MAX_PAGES_EXTRACT),
        "scanned_pages":        scanned,
        "extraction_engine":    "pymupdf",
        "extraction_available": True,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_FALLBACK_TEXT = (
    "[PDF stored successfully.  Text extraction requires PyMuPDF.  "
    "Install with: pip install pymupdf]"
)


def extract_text_from_pdf(path: Path) -> dict[str, Any]:
    """
    Extract text from a PDF file.

    Returns a dict with:
        text                 str   — extracted text, or informational fallback
        page_count           int   — total pages (0 if unreadable)
        pages_extracted      int   — pages actually processed
        scanned_pages        int   — pages with no native text (may have been OCR'd)
        extraction_engine    str   — "pymupdf" | "fallback"
        extraction_available bool  — True when real extraction ran
    """
    try:
        import fitz  # noqa: F401  — probe import
        return _extract_with_pymupdf(path)

    except ImportError:
        logger.info(
            "PyMuPDF not installed — PDF text extraction disabled.  "
            "Run: pip install pymupdf"
        )
    except Exception as exc:
        logger.warning("PDF extraction failed for '%s': %s", path.name, exc)

    # Attempt a rough page count even without PyMuPDF (by scanning %%EOF / page markers)
    page_count = _guess_page_count(path)

    return {
        "text":                 _FALLBACK_TEXT,
        "page_count":           page_count,
        "pages_extracted":      0,
        "scanned_pages":        0,
        "extraction_engine":    "fallback",
        "extraction_available": False,
    }


def _guess_page_count(path: Path) -> int:
    """
    Estimate page count by scanning raw PDF bytes for /Type /Page markers.
    Rough but dependency-free.  Returns 0 on any error.
    """
    try:
        raw = path.read_bytes()
        # Count '/Type /Page' occurrences (standard page object marker)
        count = raw.count(b"/Type /Page")
        # Also count /Type/Page (no space variant)
        count += raw.count(b"/Type/Page")
        return max(count, 0)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Availability probe (used in startup diagnostics)
# ---------------------------------------------------------------------------

def pymupdf_available() -> bool:
    """Return True if PyMuPDF (fitz) can be imported."""
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False
