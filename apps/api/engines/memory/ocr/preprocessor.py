"""
Image preprocessing pipeline for optimal OCR accuracy on UI screenshots.
Sequence: resize → denoise → contrast enhance → sharpen → binarize (optional)
"""
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


def preprocess_for_ocr(image: Image.Image, max_width: int = 2560) -> Image.Image:
    """Pipeline tuned for UI screenshots: high contrast, crisp text."""
    img = image.convert("RGB")

    # Resize only if larger than max (OCR quality degrades at massive res)
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)

    # Convert to numpy for OpenCV operations
    arr = np.array(img)

    # Mild denoise — preserves text edges better than strong denoising
    arr = cv2.fastNlMeansDenoisingColored(arr, None, h=3, templateWindowSize=7, searchWindowSize=21)

    img = Image.fromarray(arr)

    # Contrast enhancement — critical for faded UI text
    img = ImageEnhance.Contrast(img).enhance(1.3)
    img = ImageEnhance.Sharpness(img).enhance(1.5)

    return img


def to_numpy_rgb(image: Image.Image) -> np.ndarray:
    return np.array(image.convert("RGB"))
