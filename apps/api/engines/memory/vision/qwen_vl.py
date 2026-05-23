"""
Qwen2-VL visual context extractor via Ollama REST API.

Runs AFTER OCR in the pipeline. Produces a natural-language description
of what's happening on screen — not just what text is there.

Examples of what Qwen2-VL adds beyond OCR:
  OCR: "def forward(self x) return self.layers"
  VL:  "Developer is writing a PyTorch neural network forward pass in VSCode,
        file: model.py, around 60% complete"

Graceful degradation: if Ollama is unreachable, returns None and pipeline continues.
"""
import base64
import io
import logging

import httpx
from PIL import Image

from apps.api.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are EIDOLON's screen analysis engine. "
    "Describe what the user is doing on screen in 2-3 sentences. "
    "Be specific: what app, what task, what content. "
    "Focus on intent and context, not just visible text."
)


def _image_to_base64(image: Image.Image, max_size: int = 1024) -> str:
    """Resize and encode image to base64 for Ollama vision API."""
    img = image.copy()
    if img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


async def analyze_screenshot(image: Image.Image) -> str | None:
    """
    Send screenshot to Qwen2-VL via Ollama and get a contextual description.
    Returns None if Ollama is unavailable or VL is disabled.
    """
    if not settings.vl_enabled:
        return None

    try:
        img_b64 = _image_to_base64(image)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.qwen_vl_model,
                    "prompt": "Describe what the user is doing on screen. Be concise and specific.",
                    "images": [img_b64],
                    "system": _SYSTEM_PROMPT,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "num_predict": 150,
                    },
                },
            )

        if response.status_code == 200:
            data = response.json()
            return data.get("response", "").strip() or None
        else:
            logger.warning("Qwen2-VL HTTP %d: %s", response.status_code, response.text[:200])
            return None

    except httpx.ConnectError:
        logger.debug("Ollama not reachable — visual analysis skipped.")
        return None
    except Exception as e:
        logger.warning("Qwen2-VL error: %s", e)
        return None
