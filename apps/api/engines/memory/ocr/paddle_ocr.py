"""
PaddleOCR engine — singleton pattern, lazy init.

IMPORTANT: PaddlePaddle only supports Python 3.8–3.12.
When running under Python 3.14, this module will fail to import.
Solution: run Celery workers in a Python 3.12 venv (.venv-312).
The FastAPI server (which doesn't import this directly) can run on 3.14.

PaddleOCR advantages over EasyOCR for UI screenshots:
- Layout analysis: detects columns, tables, reading order
- Better accuracy on mixed UI elements (buttons, labels, code)
- angle classifier handles rotated text
"""
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from apps.api.engines.memory.ocr.preprocessor import preprocess_for_ocr, to_numpy_rgb

logger = logging.getLogger(__name__)


@dataclass
class OCRBlock:
    text: str
    confidence: float
    bbox: list              # [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    reading_order: int


@dataclass
class OCRResult:
    raw_text: str           # concatenated, reading-order sorted
    blocks: list[OCRBlock]
    mean_confidence: float
    word_count: int


class PaddleOCREngine:
    def __init__(self, language: str = "en", use_gpu: bool = False, use_angle_cls: bool = True) -> None:
        from paddleocr import PaddleOCR
        logger.info("Initializing PaddleOCR (lang=%s, gpu=%s) ...", language, use_gpu)
        self._ocr = PaddleOCR(
            use_angle_cls=use_angle_cls,
            lang=language,
            use_gpu=use_gpu,
            show_log=False,
        )
        self._threshold = 0.4
        logger.info("PaddleOCR ready.")

    def read_image(self, image: Image.Image) -> OCRResult:
        preprocessed = preprocess_for_ocr(image)
        arr = to_numpy_rgb(preprocessed)

        results = self._ocr.ocr(arr, cls=True)
        if not results or not results[0]:
            return OCRResult(raw_text="", blocks=[], mean_confidence=0.0, word_count=0)

        blocks: list[OCRBlock] = []
        for idx, line in enumerate(results[0]):
            bbox, (text, conf) = line
            if conf >= self._threshold and text.strip():
                blocks.append(OCRBlock(
                    text=text.strip(),
                    confidence=round(conf, 4),
                    bbox=bbox,
                    reading_order=idx,
                ))

        # Sort by reading order (top-to-bottom, left-to-right via Y then X of top-left corner)
        blocks.sort(key=lambda b: (b.bbox[0][1], b.bbox[0][0]))

        raw_text = " ".join(b.text for b in blocks)
        mean_conf = (
            sum(b.confidence for b in blocks) / len(blocks) if blocks else 0.0
        )

        return OCRResult(
            raw_text=raw_text,
            blocks=blocks,
            mean_confidence=round(mean_conf, 4),
            word_count=len(raw_text.split()),
        )

    def read_file(self, path: Path) -> OCRResult:
        return self.read_image(Image.open(path))


@lru_cache(maxsize=1)
def get_ocr_engine() -> PaddleOCREngine:
    from apps.api.config import settings
    return PaddleOCREngine(
        language=settings.ocr_language,
        use_gpu=settings.ocr_use_gpu,
        use_angle_cls=settings.ocr_use_angle_cls,
    )
