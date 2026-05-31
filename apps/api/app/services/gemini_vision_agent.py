"""
GeminiVisionAgent — Phase 21 (updated: google-genai new SDK).

Analyses images (screenshots, camera frames, uploaded photos) using Gemini.
Uses google-genai (new SDK).  Falls back to heuristic analysis when:
  - google-genai is not installed
  - GEMINI_API_KEY is missing
  - The API call fails

Image bytes are passed as raw bytes via Part.from_bytes — the SDK handles
binary encoding internally.  The old base64-encode-then-decode pattern was
incorrect and caused API rejections.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_VISION_PROMPT = (
    "You are an AI assistant analysing a computer screenshot or image for a personal "
    "productivity tool. Describe in ONE short paragraph:\n"
    "1. What is visible on screen (apps, windows, documents)\n"
    "2. The probable task or activity the user is performing\n"
    "3. Any notable objects, text snippets, or entities visible\n"
    "Be concise (max 80 words). Do not invent information not present in the image."
)


class GeminiVisionAgent:

    def __init__(self) -> None:
        from app.core.config import GEMINI_API_KEY, GEMINI_MODEL

        self._api_key    = GEMINI_API_KEY.strip()
        self._model_name = GEMINI_MODEL.strip() or "gemini-2.0-flash"
        self._active     = False
        self._client     = None

        if not self._api_key or self._api_key == "your_free_ai_studio_key_here":
            logger.debug("GeminiVisionAgent: no API key — heuristic mode")
            return

        try:
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
            self._active = True
            logger.info("GeminiVisionAgent: model=%s", self._model_name)
        except ImportError:
            logger.debug("GeminiVisionAgent: google-genai not installed")
        except Exception as exc:
            logger.warning("GeminiVisionAgent: init failed — %s", exc)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def is_active(self) -> bool:
        return self._active

    def analyse_image_path(self, image_path: str | Path) -> dict[str, Any]:
        """Analyse an image file. Returns a result dict."""
        path = Path(image_path)
        if not path.exists():
            return self._heuristic_result(str(image_path), error="file not found")

        if self._active:
            try:
                return self._gemini_analyse(path)
            except Exception as exc:
                logger.warning("GeminiVisionAgent: vision call failed (%s) — heuristic", exc)

        return self._heuristic_result(str(image_path))

    def analyse_image_bytes(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
        label: str = "image",
    ) -> dict[str, Any]:
        """Analyse raw image bytes."""
        if self._active:
            try:
                return self._gemini_analyse_bytes(image_bytes, mime_type)
            except Exception as exc:
                logger.warning("GeminiVisionAgent: bytes analyse failed (%s)", exc)

        return self._heuristic_result(label)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _gemini_analyse(self, path: Path) -> dict[str, Any]:
        return self._gemini_analyse_bytes(path.read_bytes(), _mime_for(path.suffix))

    def _gemini_analyse_bytes(
        self, image_bytes: bytes, mime_type: str
    ) -> dict[str, Any]:
        from google.genai import types as genai_types

        # Pass raw bytes — SDK handles encoding internally.
        # Do NOT base64-encode; the old code did this incorrectly.
        image_part = genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        response = self._client.models.generate_content(  # type: ignore[union-attr]
            model=self._model_name,
            contents=[_VISION_PROMPT, image_part],
            config=genai_types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=200,
            ),
        )
        description = (response.text or "").strip()
        return {
            "scene":      description,
            "activity":   _extract_activity(description),
            "objects":    [],
            "source":     "gemini",
            "model":      self._model_name,
            "confidence": 0.85,
        }

    @staticmethod
    def _heuristic_result(label: str, error: str = "") -> dict[str, Any]:
        try:
            from app.services.vision_intelligence_service import VisionIntelligenceService
            svc  = VisionIntelligenceService()
            meta = svc.analyse_screenshot(label)
            return {
                "scene":      meta.get("scene_type", "unknown"),
                "activity":   meta.get("probable_task", ""),
                "objects":    meta.get("active_tools", []),
                "source":     "heuristic",
                "confidence": 0.55,
                "error":      error,
            }
        except Exception:
            return {
                "scene":      "unknown",
                "activity":   "",
                "objects":    [],
                "source":     "heuristic",
                "confidence": 0.0,
                "error":      error,
            }


def _mime_for(suffix: str) -> str:
    return {
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png":  "image/png",
        ".webp": "image/webp",
        ".bmp":  "image/bmp",
        ".gif":  "image/gif",
    }.get(suffix.lower(), "image/png")


def _extract_activity(description: str) -> str:
    if not description:
        return ""
    first = description.split(".")[0].strip()
    return first[:120]
