"""Generate reviewable room-polygon drafts for commercial dataset pages.

Drafts are intentionally separate from official annotations. The heuristic
detector can suggest room regions, but it cannot reliably label OCR dimensions,
structures, or installer outcomes without review.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
warnings.filterwarnings("ignore", category=Image.DecompressionBombWarning)

from app import detect_rooms
from floorplan_text import (
    _ROOM_LABEL_ONLY_RE,
    attach_ocr_to_rooms,
    extract_pdf_text_items,
    merge_text_items,
    parse_dimension_pair,
    select_ocr_review_items,
)
from ocr_room_labels import extract_room_text


def _bbox_rect(points: list[list[float]]) -> list[float]:
    """Convert a quadrilateral to the annotation schema's [x0,y0,x1,y1] box."""
    return [
        min(point[0] for point in points),
        min(point[1] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
    ]


def _dimension_annotations(room: dict) -> list[dict]:
    """Convert extracted room measurements to reviewable schema-shaped items."""
    annotations = []
    for measurement in room.get("printed_dimensions", []):
        bbox = measurement.get("bbox")
        if not bbox:
            continue
        parsed = parse_dimension_pair(measurement.get("text", ""))
        if not parsed:
            continue

        length_m = parsed.get("length_m")
        width_m = parsed.get("width_m")
        values = parsed.get("values", [])
        unit = "m" if length_m is not None and width_m is not None else "unknown"
        dimension_values = (
            (length_m, width_m)
            if unit == "m"
            else (values[0], values[1]) if len(values) >= 2 else (None, None)
        )
        for dimension_type, value in zip(("length", "width"), dimension_values):
            annotations.append({
                "text": measurement["text"],
                "value": value,
                "bbox": _bbox_rect(bbox),
                "associated_room": room["id"],
                "type": dimension_type,
                "unit": unit,
            })
    return annotations


def generate_project(
    project_dir: Path, output_name: str, include_text: bool = True
) -> tuple[int, int]:
    pages_dir = project_dir / "pages"
    output_dir = project_dir / output_name
    output_dir.mkdir(exist_ok=True)
    metadata = json.loads((project_dir / "metadata.json").read_text(encoding="utf-8"))
    pdf_path = project_dir / "original.pdf"
    pdf_bytes = pdf_path.read_bytes() if include_text and pdf_path.is_file() else None
    total_rooms = 0
    total_pages = 0

    for page_path in sorted(pages_dir.glob("page_*.png")):
        page_number = int(page_path.stem.split("_")[-1])
        with Image.open(page_path) as image:
            image = image.convert("RGB")
            _, rooms = detect_rooms(image)
            text_items = []
            if include_text:
                if pdf_bytes:
                    text_items.extend(
                        extract_pdf_text_items(pdf_bytes, image.size, page_number - 1)
                    )
                text_items = merge_text_items(
                    text_items,
                    extract_room_text(image),
                )
                rooms = attach_ocr_to_rooms(rooms, text_items)

            room_records = []
            dimensions = []
            text_labels = []
            for index, room in enumerate(rooms, 1):
                room_id = f"P{page_number:02d}-R{index:02d}"
                suggested_label = room.get("room_name")
                room_records.append({
                    "id": room_id,
                    "polygon": room["polygon"],
                    "label": "UNREVIEWED_ROOM",
                    "confidence": None,
                    "suggested_label": suggested_label,
                })
                for item in room.get("ocr_text", []):
                    if (
                        suggested_label
                        and _ROOM_LABEL_ONLY_RE.fullmatch(suggested_label)
                        and suggested_label.casefold() in item["text"].casefold()
                    ):
                        text_labels.append({
                            "text": item["text"],
                            "bbox": _bbox_rect(item["bbox"]),
                            "label": suggested_label,
                            "type": "room_name",
                        })
                room["id"] = room_id
                dimensions.extend(_dimension_annotations(room))

            draft = {
                "page_number": page_number,
                "image_width": image.width,
                "image_height": image.height,
                "source_pdf": metadata["source_pdf"],
                "annotator": "AUTO_DRAFT_REQUIRES_REVIEW",
                "timestamp": metadata["created_at"],
                "rooms": room_records,
                "dimensions": dimensions,
                "text_labels": text_labels,
                "structural_elements": [],
                "table_rows": [],
                "draft_status": "review_required",
                "detector_candidate_count": len(rooms),
                "text_source_count": len(text_items),
                "ocr_review_items": select_ocr_review_items(text_items),
            }
        (output_dir / page_path.name.replace(".png", ".json")).write_text(
            json.dumps(draft, indent=2) + "\n", encoding="utf-8"
        )
        total_pages += 1
        total_rooms += len(rooms)
    return total_pages, total_rooms


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reviewable room annotation drafts.")
    parser.add_argument("--dataset-root", default="commercial_dataset")
    parser.add_argument("--output-name", default="annotation_drafts")
    parser.add_argument(
        "--skip-text",
        action="store_true",
        help="Skip PDF text and OCR enrichment; generate room polygons only.",
    )
    args = parser.parse_args()
    root = Path(args.dataset_root) / "projects"
    projects = sorted(path for path in root.iterdir() if path.is_dir())
    pages = rooms = 0
    for project in projects:
        project_pages, project_rooms = generate_project(
            project, args.output_name, include_text=not args.skip_text
        )
        pages += project_pages
        rooms += project_rooms
        print(f"{project.name}: pages={project_pages}, draft_rooms={project_rooms}")
    print(f"SUMMARY projects={len(projects)}, pages={pages}, draft_rooms={rooms}")


if __name__ == "__main__":
    main()