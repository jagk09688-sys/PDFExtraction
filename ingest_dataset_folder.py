"""Import unique PDFs from a folder into the commercial project dataset."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from create_project_dataset import MANIFEST_FIELDS, create_project


def project_id_for(pdf_path: Path) -> str:
    legacy_ids = {
        "Floor Plan (2)": "FP-FLOORPLAN2",
        "FP1": "FP1",
        "FP2": "FP2",
        "FP3": "FP3",
        "FP5": "FP5",
        "FP7": "FP7",
    }
    if pdf_path.stem in legacy_ids:
        return legacy_ids[pdf_path.stem]
    value = re.sub(r"[^A-Za-z0-9]+", "-", pdf_path.stem).strip("-").upper()
    return f"PLAN-{value or 'UNNAMED'}"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rebuild_manifest(dataset_root: Path) -> None:
    rows = []
    for metadata_path in sorted((dataset_root / "projects").glob("*/metadata.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        rows.append({
            "project_id": metadata["project_id"],
            "source_pdf": metadata["source_pdf"],
            "status": metadata["status"],
            "page_count": metadata["pages"]["count"],
            "room_count": len(metadata["rooms"]),
            "has_room_annotations": metadata["annotation"]["status"] == "complete",
            "has_estimator_outcome": metadata["estimator_outcome"]["lm_ordered"] is not None,
            "has_installer_feedback": metadata["installer_feedback"]["received"],
            "created_at": metadata["created_at"],
        })
    rows.sort(key=lambda row: row["project_id"])
    manifest_path = dataset_root / "projects.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def ingest(input_dir: Path, dataset_root: Path, dpi: int) -> None:
    seen_hashes: set[str] = set()
    imported = skipped = duplicates = 0
    for pdf_path in sorted(input_dir.glob("*.pdf")):
        digest = file_hash(pdf_path)
        if digest in seen_hashes:
            duplicates += 1
            print(f"SKIP duplicate content: {pdf_path.name}")
            continue
        seen_hashes.add(digest)

        project_id = project_id_for(pdf_path)
        project_dir = dataset_root / "projects" / project_id
        if project_dir.exists():
            skipped += 1
            print(f"SKIP existing project: {project_id}")
            continue
        try:
            create_project(pdf_path, dataset_root, project_id, dpi, "Imported from Dataset folder")
        except PermissionError as exc:
            if "projects.csv" not in str(exc):
                raise
            print("WARNING projects.csv is locked; project files were created and manifest update is deferred")
        imported += 1
        print(f"IMPORTED {project_id}: {pdf_path.name}")
    try:
        rebuild_manifest(dataset_root)
        print("Manifest rebuilt successfully")
    except PermissionError:
        print("WARNING projects.csv is locked; close Excel and rerun this command to rebuild the manifest")
    print(f"Summary: imported={imported}, existing={skipped}, duplicates={duplicates}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import unique Dataset PDFs into commercial_dataset.")
    parser.add_argument("--input-dir", default="Dataset")
    pars