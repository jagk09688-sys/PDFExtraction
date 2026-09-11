"""Optional OCR helpers for floorplan text extraction.

This module provides a lightweight OCR wrapper using Surya when available,
with a fallback to PaddleOCR if installed and a graceful no-op otherwise.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def extract_text_with_surya(image_path: str | Path):
    """Extract text using Surya OCR if the package is installed."""
    try:
        from surya.ocr import OCR
    except Exception:
        return []

    try:
        model = OCR()
        results = model(image_path)
        texts = []
        for item in results:
            texts.append(
                {
                    'text': getattr(item, 'text', ''),
                    'bbox': getattr(item, 'bbox', None),
                    'confidence': getattr(item, 'confidence', 0.0),
                }
            )
        return texts
    except Exception as exc:
        print(f"Surya OCR failed: {exc}")
        return []


def extract_text_with_paddleocr(image_path: str | Path):
    """Extract text using PaddleOCR if the package is installed."""
    try:
        from paddleocr import PaddleOCR
    except Exception:
        return []

    try:
        ocr = PaddleOCR(use_angle_cls=True, lang='en')
        result = ocr.ocr(str(image_path), cls=True)
        texts = []
        for line in result:
            for item in line:
                texts.append(
                    {
                        'text': item[1][0],
                        'bbox': item[0],
                        'confidence': float(item[1][1]),
                    }
                )
        return texts
    except Exception as exc:
        print(f"PaddleOCR failed: {exc}")
        return []


def extract_room_text(image_path: str | Path, prefer: str = 'surya'):
    """Return OCR text results from the preferred OCR engine.

    prefer can be 'surya' or 'paddleocr'.
    """
    image_path = Path(image_path)
    if prefer.lower() == 'paddleocr':
        return extract_text_with_paddleocr(image_path)

    surya_results = extract_text_with_surya(image_path)
    if surya_results:
        return surya_results

    return extract_text_with_paddleocr(image_path)
