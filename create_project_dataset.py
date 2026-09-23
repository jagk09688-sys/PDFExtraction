"""Create a project record for the commercial carpet dataset.

Each project keeps the source PDF untouched and stores derived pages, labels,
and estimator outcomes alongside a metadata record. The metadata is deliberately
truthful: unknown measurements remain null until they are supplied.

Example:
    python create_project_dataset.py --pdf Dataset/FP1.pdf --project-id FP1
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf


MANIFEST_FIELDS = [
    "project_id",
    "source_pdf",
    "status",
    "page_count",
    "room_count",
    "has_room_annotations",
    "has_estimator_outcome",
    "has_installer_feedback",
    "created_at",
]


def render_pages(pdf_path: Path, pages_dir: Path, dpi: int) -> int:
    document = pymupdf.open(pdf_path)
    zoom = dpi / 72.0
    matrix = pymupdf.Matrix(zoom, zoom)
    try:
        for page_number, page in enumerate(document, 1):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            pixmap.save(str(pages_dir / f"page_{page_number:03d}.png"))
        return len(document)
    finally:
        document.close()


def write_annotation_templates(
    project_dir: Path, source_pdf: str, page_count: int, annotator: str = "UNASSIGNED"
) -> None:
    pages_dir = project_dir / "pages"
    annotations_dir = project_dir / "annotations"
    timestamp = datetime.now(timezone.utc).isoformat()
    for page_number in range(1, page_count + 1):
        page_path = pages_dir / f"page_{page_number:03d}.png"
        from PIL import Image

        with Image.open(page_path) as image:
            template = {
                "page_number": page_number,
                "image_width": image.width,
                "image_height": image.height,
                "source_pdf": source_pdf,
                "annotator": annotator,
                "timestamp": timestamp,
                "rooms": [],
                "dimensions": [],
                "structural_elements": [],
                "table_rows": [],
            }
        output = annotations_dir / f"page_{page_number:03d}.json"
        output.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")


def create_project(pdf_path: Path, dataset_root: Path, project_id: str, dpi: int, notes: str) -> Path:
    pdf_path = pdf_path.resolve()
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    project_dir = dataset_root / "projects" / project_id
    if project_dir.exists():
        raise FileExistsError(f"Project already exists: {project_dir}")

    pages_dir = project_dir / "pages"
    annotations_dir = project_dir / "annotations"
    masks_dir = project_dir / "masks"
    layouts_dir = project_dir / "final_layouts"
    for directory in (pages_dir, annotations_dir, masks_dir, layouts_dir):
        directory.mkdir(parents=True, exist_ok=True)

    shutil.copy2(pdf_path, project_dir / "original.pdf")
    page_count = render_pages(pdf_path, pages_dir, dpi)
    write_annotation_templates(project_dir, pdf_path.name, page_count)
    created_at = datetime.now(timezone.utc).isoformat()

    metadata = {
        "project_id": project_id,
        "source_pdf": pdf_path.name,
        "created_at": created_at,
        "status": "collected",
        "notes": notes,
        "pages": {"count": page_count, "render_dpi": dpi},
        "rooms": [],
        "estimator_outcome": {
            "roll_width_m": None,
            "lm_ordered": None,
            "waste_percent": None,
            "join_positions": [],
            "offcut_reuse_decisions": [],
        },
        "installer_feedback": {"received": False, "notes": ""},
        "annotation": {
            "status": "not_started",
            "tool": "LabelMe",
            "room_labels": [],
        },
    }
    (project_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    update_manifest(dataset_root, metadata)
    return project_dir


def update_manifest(dataset_root: Path, metadata: dict) -> None:
    manifest_path = dataset_root / "projects.csv"
    rows = []
    if manifest_path.exists():
        with manifest_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

    row = {
        "project_id": metadata["project_id"],
        "source_pdf": metadata["source_pdf"],
        "status": metadata["status"],
        "page_count": metadata["pages"]["count"],
        "room_count": len(metadata["rooms"]),
        "has_room_annotations": metadata["annotation"]["status"] == "complete",
        "has_estimator_outcome": metadata["estimator_outcome"]["lm_ordered"] is not None,
        "has_installer_feedback": metadata["installer_feedback"]["received"],
        "created_at": metadata["created_at"],
    }
    rows = [existing for existing in rows if existing.get("project_id") != row["project_id"]]
    rows.append({field: str(row[field]) for field in MANIFEST_FIELDS})
    rows.sort(key=lambda item: item["project_id"])
    dataset_root.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a commercial carpet project dataset record.")
    parser.add_argument("--pdf", required=True, help="Source floor-plan PDF")
    parser.add_argument("--project-id", required=True, help="Stable ID, for example CW-0001")
    parser.add_argument("--dataset-root", default="commercial_dataset")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    project_dir = create_project(Path(args.pdf), Path(args.dataset_root), args.project_id, args.dpi, args.notes)
    print(f"Created {project_dir}")


if __name__ == "__main__":
    main()