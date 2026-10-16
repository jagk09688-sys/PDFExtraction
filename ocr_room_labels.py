"""Optional OCR helpers for floorplan text extraction.

This module provides a lightweight OCR wrapper using Surya when available,
with a fallback to PaddleOCR if installed and a graceful no-op otherwise.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image


_rapid_ocr_engine = None
_ROOM_WORD_RE = re.compile(
    r"\b(?:bed(?:room)?|bath(?:room)?|wc|ensuite|en\s*suite|kitchen|living|lounge|"
    r"dining|hall|hallway|corridor|passage|study|rumpus|robe|laundry|utility|garage|"
    r"office|meeting(?:\s*room)?|board\s*room|conference|reception|breakout|"
    r"classroom|consulting|treatment|waiting|lobby|showroom|warehouse|workshop|"
    r"staff(?:\s*room)?|work\s*room|store(?:\s*room)?|storage|pantry|linen|"
    r"plant\s*room|server\s*room|comms|electrical|mechanical|accessible|"
    r"disabled|print\s*room|copy\s*room|tea\s*room|entry|porch|verandah)\b",
    re.IGNORECASE,
)


def ocr_engine_available() -> bool:
    """Return whether a supported OCR package is importable."""
    for module_name in ("rapidocr", "rapidocr_onnxruntime", "surya", "paddleocr"):
        try:
            if importlib.util.find_spec(module_name) is not None:
                return True
        except (ImportError, ValueError):
            continue
    return False


def extract_text_with_rapidocr(image_path: str | Path):
    """Extract text and quadrilateral boxes with the CPU-friendly RapidOCR engine."""
    global _rapid_ocr_engine
    try:
        from rapidocr import RapidOCR
    except Exception:
        return []

    try:
        if _rapid_ocr_engine is None:
            _rapid_ocr_engine = RapidOCR()
        if isinstance(image_path, Image.Image):
            source = np.asarray(image_path.convert("RGB"))
        else:
            with Image.open(image_path) as pil_image:
                source = np.asarray(pil_image.convert("RGB"))

        source_height, source_width = source.shape[:2]
        max_dimension = 3000
        scale = min(1.0, max_dimension / max(source_height, source_width))
        if scale < 1.0:
            ocr_image = cv2.resize(
                source,
                (max(1, round(source_width * scale)), max(1, round(source_height * scale))),
                interpolation=cv2.INTER_AREA,
            )
        else:
            ocr_image = source

        best_items = []
        best_score = float("-inf")
        best_rotation = 0
        # Scanned plans can be upside down or sideways. Compare text content,
        # favoring known room-name words, then map boxes to original pixels.
        quarter_turn_options = (1, 3) if source_width > source_height else (0, 2)
        for quarter_turns in quarter_turn_options:
            oriented = np.rot90(ocr_image, k=quarter_turns).copy() if quarter_turns else ocr_image
            result = _rapid_ocr_engine(oriented)
            boxes = getattr(result, "boxes", None)
            texts = getattr(result, "txts", None)
            scores = getattr(result, "scores", None)
            if boxes is None or texts is None:
                continue

            items = []
            confidence_total = 0.0
            room_hits = 0
            dimension_hits = 0
            oriented_height, oriented_width = oriented.shape[:2]
            for index, (box, text) in enumerate(zip(boxes, texts)):
                text = str(text).strip()
                if not text:
                    continue
                confidence = float(scores[index]) if scores is not None and index < len(scores) else None
                points = np.asarray(box, dtype=np.float32).reshape((-1, 2))
                points /= scale
                if quarter_turns == 1:
                    points = np.column_stack((source_width - points[:, 1], points[:, 0]))
                elif quarter_turns == 2:
                    points = np.column_stack((source_width - points[:, 0], source_height - points[:, 1]))
                elif quarter_turns == 3:
                    points = np.column_stack((points[:, 1], source_height - points[:, 0]))
                points[:, 0] = np.clip(points[:, 0], 0, source_width)
                points[:, 1] = np.clip(points[:, 1], 0, source_height)
                items.append({
                    "bbox": points.tolist(),
                    "text": text,
                    "confidence": confidence,
                    "ocr_rotation": quarter_turns * 90,
                })
                if _ROOM_WORD_RE.search(text):
                    room_hits += 1
                if re.search(r"\d\s*[x×]\s*\d|\d\s*(?:mm|cm|m\b)", text, re.IGNORECASE):
                    dimension_hits += 1
                confidence_total += confidence or 0.0

            # Room vocabulary is a strong orientation clue; confidence and
            # text count provide a stable tie-break for other drawing text.
            score = room_hits * 100 + dimension_hits * 8 + confidence_total + len(items) * 0.05
            if score > best_score:
                best_items = items
                best_score = score
                best_rotation = quarter_turns * 90

        for item in best_items:
            item["selected_page_rotation"] = best_rotation
        return best_items
    except Exception as exc:
        print(f"RapidOCR failed: {exc}")
        return []


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


def extract_room_text(image_path: str | Path | Image.Image, prefer: str = 'rapidocr'):
    """Return OCR text results from the preferred OCR engine.

    prefer can be 'surya' or 'paddleocr'.
    """
    if prefer.lower() == 'rapidocr':
        results = extract_text_with_rapidocr(image_path)
        if results:
            return results
    if isinstance(image_path, Image.Image):
        return []

    image_path = Path(image_path)
    if prefer.lower() == 'paddleocr':
        return extract_text_with_paddleocr(image_path)

    surya_results = extract_text_with_surya(image_path)
    if surya_results:
        return surya_results

    return extract_text_with_paddleocr(image_path)
