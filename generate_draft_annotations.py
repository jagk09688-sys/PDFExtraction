"""Generate reviewable room-polygon drafts for commercial dataset pages.

Drafts are intentionally separate from official annotations. The heuristic
detector can suggest room regions, but it cannot reliably label OCR dimensions,
structures, or installer outcomes without review.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from app import detect_rooms


def generate_project(project_dir: Path, output_name: str) -> tuple[int, int]:
    pages_dir = project_dir / "pages"
    output_dir = project_dir / output_name
    output_dir.mkdir(exist_ok=True)
    metadata = json.loads((project_dir / "metadata.json").read_text(encoding="utf-8"))
    total_rooms = 0
    total_pages = 0

    for page_path in sorted(pages_dir.glob("page_*.png")):
        page_number = int(page_path.stem.split("_")[-1])
        with Image.open(page_path) as image:
            image = image.convert("RGB")
            _, rooms = detect_rooms(image)
            draft = {
                "page_number": page_number,
                "image_width": image.width,
                "image_height": image.height,
                "source_pdf": metadata["source_pdf"],
                "annotator": "AUTO_DRAFT_REQUIRES_REVIEW",
                "timestamp": metadata["created_at"],
                "rooms": [
                    {
                        "id": f"P{page_number:02d}-R{index:02d}",
                        "polygon": room["polygon"],
                        "label": "UNREVIEWED_ROOM",
                        "confidence": None,
                    }
                    for index, room in enumerate(rooms, 1)
                ],
                "dimensions": [],
                "text_labels": [],
                "structural_elements": [],
                "table_rows": [],
                "draft_status": "review_required",
                "detector_candidate_count": len(rooms),
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
    args = parser.parse_args()
    root = Path(args.dataset_root) / "projects"
    projects = sorted(path for path in root.iterdir() if path.is_dir())
    pages = rooms = 0
    for project in projects:
        project_pages, project_rooms = generate_project(project, args.output_name)
        pages += project_pages
        rooms += project_rooms
        print(f"{project.name}: pages={project_pages}, draft_rooms={project_rooms}")
    print(f"SUMMARY projects={len(projects)}, pages={pages}, draft_rooms={rooms}")


if __name__ == "__main__":
    main()