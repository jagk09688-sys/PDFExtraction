"""Utilities for attaching OCR words and printed dimensions to detected rooms."""

from __future__ import annotations

import re
from typing import Any

import cv2
import numpy as np


_NUMBER = r"\d{1,4}(?:[.,]\d{1,3})?"
_UNIT = r"mm|cm|m|ft|in|['\"]"
_SINGLE_MEASURE_RE = re.compile(
    rf"(?<![\w.])(?P<value>{_NUMBER})\s*(?P<unit>mm|cm|m|ft|in|['\"])(?![\w])",
    re.IGNORECASE,
)
_PAIR_RE = re.compile(
    rf"(?<![\w.])(?P<a>{_NUMBER})\s*(?P<ua>{_UNIT})?\s*[x×]\s*"
    rf"(?P<b>{_NUMBER})\s*(?P<ub>{_UNIT})?(?![\w.])",
    re.IGNORECASE,
)
_FEET_INCHES = re.compile(
    r"(?<!\w)(\d+(?:\.\d+)?)\s*'\s*(?:-\s*(\d+(?:\.\d+)?)\s*(?:\"|in)?)?\s*[x×]\s*"
    r"(\d+(?:\.\d+)?)\s*'\s*(?:-\s*(\d+(?:\.\d+)?)\s*(?:\"|in)?)?",
    re.IGNORECASE,
)

_UNIT_TO_METRES = {
    "mm": 0.001,
    "cm": 0.01,
    "m": 1.0,
    "ft": 0.3048,
    "'": 0.3048,
    "in": 0.0254,
    '"': 0.0254,
}
_ROOM_NAME_RE = re.compile(
    r"\b(?:bed(?:room)?|bath(?:room)?|wc|ensuite|en\s*suite|kitchen|living|lounge|"
    r"dining|hall|hallway|corridor|passage|study|rumpus|robe|laundry|utility|garage|"
    r"office|meeting(?:\s*room)?|board\s*room|conference|reception|breakout|"
    r"classroom|consulting|treatment|waiting|lobby|showroom|warehouse|workshop|"
    r"staff(?:\s*room)?|work\s*room|store(?:\s*room)?|storage|pantry|linen|"
    r"plant\s*room|server\s*room|comms|electrical|mechanical|accessible|"
    r"disabled|print\s*room|copy\s*room|tea\s*room|entry|porch|verandah)(?![A-Za-z])",
    re.IGNORECASE,
)
_NON_ROOM_LABEL_RE = re.compile(
    r"\b(?:date|revision|construction|elevation|north|direction|signature|drawing|dwg|"
    r"plan|client|builder|scale|sheet|page|project|address|proposed|existing|"
    r"floor\s*plan|area\s*schedule|drawing\s*number)\b",
    re.IGNORECASE,
)


def extract_pdf_text_items(
    pdf_bytes: bytes, image_size: tuple[int, int], page_number: int = 0
) -> list[dict[str, Any]]:
    """Extract selectable PDF text lines and map their boxes to rendered pixels.

    This complements OCR: born-digital plan text is usually more accurate than
    OCR, while scanned PDFs simply return no native text and remain OCR-driven.
    ``page_number`` is zero-based and ``image_size`` is ``(width, height)``.
    """
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf
        except ImportError:
            return []

    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return []

    try:
        if page_number < 0 or page_number >= len(document):
            return []

        page = document[page_number]
        page_rect = page.rect
        if page_rect.width <= 0 or page_rect.height <= 0:
            return []
        scale_x = image_size[0] / page_rect.width
        scale_y = image_size[1] / page_rect.height
        lines: dict[tuple[int, int], list[tuple[int, str, Any]]] = {}
        for word in page.get_text("words"):
            if len(word) < 8 or not str(word[4]).strip():
                continue
            key = (int(word[5]), int(word[6]))
            lines.setdefault(key, []).append((int(word[7]), str(word[4]), word[:4]))

        items = []
        for words in lines.values():
            words.sort(key=lambda word: word[0])
            text = " ".join(word[1] for word in words).strip()
            x0 = min(word[2][0] for word in words)
            y0 = min(word[2][1] for word in words)
            x1 = max(word[2][2] for word in words)
            y1 = max(word[2][3] for word in words)
            rect = pymupdf.Rect(x0, y0, x1, y1) * page.rotation_matrix
            bbox = [
                [float(rect.x0 * scale_x), float(rect.y0 * scale_y)],
                [float(rect.x1 * scale_x), float(rect.y0 * scale_y)],
                [float(rect.x1 * scale_x), float(rect.y1 * scale_y)],
                [float(rect.x0 * scale_x), float(rect.y1 * scale_y)],
            ]
            items.append(
                {"text": text, "bbox": bbox, "confidence": 1.0, "source": "pdf_text"}
            )
        return items
    finally:
        document.close()


def merge_text_items(*item_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Combine text sources, preferring native text for duplicate overlapping lines."""
    merged: list[dict[str, Any]] = []
    for group in item_groups:
        for item in group:
            text = " ".join(str(item.get("text", "")).split()).strip()
            if not text:
                continue
            candidate = {**item, "text": text}
            candidate_points = _bbox_points(candidate.get("bbox"))
            duplicate = False
            if candidate_points:
                cx = sum(point[0] for point in candidate_points) / len(candidate_points)
                cy = sum(point[1] for point in candidate_points) / len(candidate_points)
                for existing in merged:
                    if text.casefold() != existing["text"].casefold():
                        continue
                    existing_points = _bbox_points(existing.get("bbox"))
                    if not existing_points:
                        continue
                    ex = sum(point[0] for point in existing_points) / len(existing_points)
                    ey = sum(point[1] for point in existing_points) / len(existing_points)
                    if (cx - ex) ** 2 + (cy - ey) ** 2 <= 12**2:
                        duplicate = True
                        break
            if not duplicate:
                merged.append(candidate)
    return merged


def _float_value(value: str) -> float:
    return float(value.replace(",", "."))


def parse_dimension_pair(text: str) -> dict[str, Any] | None:
    """Parse a printed ``length x width`` pair without guessing missing units."""
    normalized = " ".join(str(text).replace("\u00d7", "x").split())
    normalized = re.sub(r"(?<=')\s+(?=\d)", "-", normalized)
    feet_match = _FEET_INCHES.search(normalized)
    if feet_match:
        feet_a, inches_a, feet_b, inches_b = feet_match.groups()
        values_m = [
            _float_value(feet_a) * 0.3048 + (_float_value(inches_a) if inches_a else 0) * 0.0254,
            _float_value(feet_b) * 0.3048 + (_float_value(inches_b) if inches_b else 0) * 0.0254,
        ]
        return {
            "text": str(text).strip(),
            "values": [round(value, 4) for value in values_m],
            "unit": "ft/in",
            "length_m": round(max(values_m), 4),
            "width_m": round(min(values_m), 4),
        }

    match = _PAIR_RE.search(normalized)
    if not match:
        return None

    value_a = _float_value(match.group("a"))
    value_b = _float_value(match.group("b"))
    unit_a = (match.group("ua") or "").lower()
    unit_b = (match.group("ub") or "").lower()
    # A single trailing unit applies to both values, e.g. "3.2 x 4.1 m".
    shared_unit = unit_a or unit_b
    if unit_a and unit_b and _UNIT_TO_METRES[unit_a] != _UNIT_TO_METRES[unit_b]:
        unit_a, unit_b = unit_a, unit_b
    else:
        unit_a = unit_b = shared_unit

    length_m = width_m = None
    if unit_a in _UNIT_TO_METRES and unit_b in _UNIT_TO_METRES:
        converted = [value_a * _UNIT_TO_METRES[unit_a], value_b * _UNIT_TO_METRES[unit_b]]
        length_m, width_m = max(converted), min(converted)

    values = sorted((value_a, value_b), reverse=True)
    return {
        "text": str(text).strip(),
        "values": values,
        "unit": shared_unit or None,
        "length_m": round(length_m, 4) if length_m is not None else None,
        "width_m": round(width_m, 4) if width_m is not None else None,
    }


def parse_single_measurement(text: str) -> dict[str, Any] | None:
    """Parse one printed length when OCR reads dimension labels separately."""
    normalized = " ".join(str(text).replace(",", ".").split())
    if re.fullmatch(r"\d{3,5}(?:\.\d{1,3})?", normalized):
        value = _float_value(normalized)
        return {
            "text": str(text).strip(),
            "value": value,
            "unit": "unknown",
            "value_m": None,
        }
    match = _SINGLE_MEASURE_RE.fullmatch(normalized)
    if not match:
        return None
    unit = match.group("unit").lower()
    value = _float_value(match.group("value"))
    factor = _UNIT_TO_METRES.get(unit)
    return {
        "text": str(text).strip(),
        "value": value,
        "unit": unit,
        "value_m": round(value * factor, 4) if factor is not None else None,
    }


def _bbox_points(bbox: Any) -> list[list[float]] | None:
    if isinstance(bbox, dict):
        keys = ("x1", "y1", "x2", "y2")
        if all(key in bbox for key in keys):
            x1, y1, x2, y2 = (float(bbox[key]) for key in keys)
            return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
        keys = ("left", "top", "right", "bottom")
        if all(key in bbox for key in keys):
            x1, y1, x2, y2 = (float(bbox[key]) for key in keys)
            return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4 and all(
        isinstance(value, (int, float)) for value in bbox
    ):
        x1, y1, x2, y2 = map(float, bbox)
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 3:
        try:
            return [[float(point[0]), float(point[1])] for point in bbox]
        except (TypeError, ValueError, IndexError):
            return None
    return None


def attach_ocr_to_rooms(rooms: list[dict], text_items: list[dict]) -> list[dict]:
    """Attach OCR entries only when their centers lie inside detected polygons."""
    for room in rooms:
        room["room_name"] = None
        room["ocr_text"] = []
        room["printed_dimensions"] = []
        polygon_points = room.get("polygon", [])
        polygon = np.asarray(polygon_points, dtype=np.float32).reshape((-1, 1, 2))
        if len(polygon) < 3:
            continue

        contained_items = []
        for item in text_items:
            text = " ".join(str(item.get("text", "")).split()).strip()
            bbox_points = _bbox_points(item.get("bbox"))
            if not text or not bbox_points:
                continue
            center_x = sum(point[0] for point in bbox_points) / len(bbox_points)
            center_y = sum(point[1] for point in bbox_points) / len(bbox_points)
            if cv2.pointPolygonTest(polygon, (center_x, center_y), False) >= 0:
                normalized_item = {
                    "text": text,
                    "bbox": bbox_points,
                    "confidence": item.get("confidence"),
                    "source": item.get("source", "ocr"),
                }
                contained_items.append(normalized_item)
                parsed_dimension = parse_dimension_pair(text)
                if parsed_dimension:
                    room["printed_dimensions"].append(parsed_dimension)
                else:
                    single_measure = parse_single_measurement(text)
                    if single_measure:
                        room["printed_dimensions"].append(single_measure)

        room["ocr_text"] = contained_items
        name_candidates = [
            item for item in contained_items
            if _ROOM_NAME_RE.search(item["text"])
            and parse_dimension_pair(item["text"]) is None
        ]
        if name_candidates:
            selected = max(name_candidates, key=lambda item: float(item.get("confidence") or 0))
            room["room_name"] = selected["text"]
        else:
            fallback_names = [
                item for item in contained_items
                if len(re.findall(r"[A-Za-z]{3,}", item["text"]))
                and not _NON_ROOM_LABEL_RE.search(item["text"])
                and parse_dimension_pair(item["text"]) is None
            ]
            if fallback_names:
                selected = max(fallback_names, key=lambda item: float(item.get("confidence") or 0))
                room["room_name"] = selected["text"]
    return rooms


def select_ocr_review_items(text_items: list[dict], limit: int = 100) -> list[dict]:
    """Select room-name and dimension-like OCR lines for a compact page review."""
    review_items = []
    for item in text_items:
        text = " ".join(str(item.get("text", "")).split()).strip()
        if not text:
            continue
        dimension = parse_dimension_pair(text) or parse_single_measurement(text)
        if dimension is not None:
            kind = "dimension candidate — verify units" if dimension.get("unit") in (None, "unknown") else "dimension candidate"
        elif _ROOM_NAME_RE.search(text):
            kind = "room-name candidate"
        else:
            continue
        review_items.append({
            "text": text,
            "kind": kind,
            "confidence": item.get("confidence"),
        })
    review_items.sort(
        key=lambda item: (
            0 if item["kind"] == "room-name candidate" else 1,
            -(float(item["confidence"]) if item.get("confidence") is not None else 0),
            item["text"],
        )
    )
    return review_items[:limit]
