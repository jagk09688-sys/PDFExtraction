"""Validate official page annotations and image geometry."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from PIL import Image


STRUCTURE_LABELS = {"door", "window", "wall", "stairs", "arrow", "note"}
DIMENSION_TYPES = {"length", "width", "unknown"}


def error(errors: list[str], path: str, message: str) -> None:
    errors.append(f"{path}: {message}")


def validate_page(annotation_path: Path) -> list[str]:
    errors = []
    try:
        data = json.loads(annotation_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{annotation_path}: invalid JSON ({exc})"]

    required = ["page_number", "image_width", "image_height", "source_pdf", "annotator", "timestamp", "rooms", "dimensions", "structural_elements", "table_rows"]
    for field in required:
        if field not in data:
            error(errors, field, "missing required field")
    if errors:
        return errors

    image_path = annotation_path.parent.parent / "pages" / f"page_{int(data['page_number']):03d}.png"
    if not image_path.is_file():
        error(errors, "page_number", f"image not found: {image_path.name}")
    else:
        with Image.open(image_path) as image:
            if [image.width, image.height] != [data["image_width"], data["image_height"]]:
                error(errors, "image_width/image_height", f"does not match {image.width}x{image.height}")

    try:
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    except (TypeError, ValueError):
        error(errors, "timestamp", "must be ISO-8601 date-time")

    width, height = data["image_width"], data["image_height"]
    for index, room in enumerate(data["rooms"]):
        polygon = room.get("polygon", [])
        if len(polygon) < 3 or not room.get("label"):
            error(errors, f"rooms[{index}]", "needs label and polygon with at least 3 points")
        for point in polygon:
            if len(point) != 2 or not (0 <= point[0] <= width and 0 <= point[1] <= height):
                error(errors, f"rooms[{index}].polygon", "point is outside image bounds")

    for index, dimension in enumerate(data["dimensions"]):
        if dimension.get("type") not in DIMENSION_TYPES or len(dimension.get("bbox", [])) != 4:
            error(errors, f"dimensions[{index}]", "needs valid type and bbox")

    for index, item in enumerate(data["structural_elements"]):
        if item.get("label") not in STRUCTURE_LABELS or len(item.get("bbox", [])) != 4:
            error(errors, f"structural_elements[{index}]", "needs valid label and bbox")
        if item.get("label") == "wall" and len(item.get("polygon", [])) < 3:
            error(errors, f"structural_elements[{index}].polygon", "walls require a polygon")

    for index, row in enumerate(data["table_rows"]):
        if len(row.get("bbox", [])) != 4:
            error(errors, f"table_rows[{index}].bbox", "needs four coordinates")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate official page annotation JSON files.")
    parser.add_argument("annotations_dir")
    args = parser.parse_args()
    paths = sorted(Path(args.annotations_dir).glob("page_*.json"))
    if not paths:
        raise SystemExit("No page_*.json files found")
    errors = [problem for path in paths for problem in validate_page(path)]
    if errors:
        print("INVALID")
        print("\n".join(errors))
        raise SystemExit(1)
    print(f"VALID: {len(paths)} page annotations")


if __name__ == "__main__":
    main()