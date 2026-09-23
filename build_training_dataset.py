"""Build a leakage-safe segmentation dataset from reviewed project annotations.

Only official annotations with at least one reviewed room polygon are included.
Projects, rather than individual pages, are assigned to train/validation so
pages from one floor plan cannot appear in both splits.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path

from official_annotations_to_masks import write_mask
from validate_annotations import validate_page


def build(dataset_root: Path, output_root: Path, val_ratio: float, seed: int) -> None:
    project_root = dataset_root / "projects"
    projects = sorted(path for path in project_root.iterdir() if path.is_dir())
    eligible = []
    report = {"projects": len(projects), "eligible_projects": 0, "eligible_pages": 0, "skipped": []}

    for project in projects:
        annotations = sorted((project / "annotations").glob("page_*.json"))
        valid = []
        problems = []
        for annotation in annotations:
            errors = validate_page(annotation)
            if errors:
                problems.extend(errors)
                continue
            data = json.loads(annotation.read_text(encoding="utf-8"))
            if data.get("annotator") == "AUTO_DRAFT_REQUIRES_REVIEW":
                problems.append(f"{annotation.name}: automatic draft is not eligible")
                continue
            if not data.get("rooms"):
                problems.append(f"{annotation.name}: no reviewed rooms")
                continue
            valid.append(annotation)
        if valid:
            eligible.append((project, valid))
        else:
            report["skipped"].append({"project": project.name, "reasons": problems[:5] or ["no annotations"]})

    rng = random.Random(seed)
    shuffled = eligible[:]
    rng.shuffle(shuffled)
    val_count = max(1, round(len(shuffled) * val_ratio)) if len(shuffled) > 1 else 0
    val_projects = {project.name for project, _ in shuffled[:val_count]}

    if output_root.exists():
        shutil.rmtree(output_root)
    for split in ("train", "val"):
        (output_root / split / "images").mkdir(parents=True, exist_ok=True)
        (output_root / split / "masks").mkdir(parents=True, exist_ok=True)

    for project, annotations in eligible:
        split = "val" if project.name in val_projects else "train"
        for annotation in annotations:
            data = json.loads(annotation.read_text(encoding="utf-8"))
            page_name = annotation.stem + ".png"
            image_path = project / "pages" / page_name
            if not image_path.exists():
                raise FileNotFoundError(image_path)
            output_name = f"{project.name}__{page_name}"
            shutil.copy2(image_path, output_root / split / "images" / output_name)
            mask_path = write_mask(annotation, output_root / split / "masks")
            mask_path.rename(output_root / split / "masks" / output_name)
            report["eligible_pages"] += 1

    report["eligible_projects"] = len(eligible)
    report["train_projects"] = len(eligible) - len(val_projects)
    report["val_projects"] = len(val_projects)
    report["train_pages"] = len(list((output_root / "train" / "images").glob("*.png")))
    report["val_pages"] = len(list((output_root / "val" / "images").glob("*.png")))
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "quality_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not eligible:
        raise SystemExit("No reviewed annotations available; training dataset was not created.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a reviewed, leakage-safe training dataset.")
    parser.add_argument("--dataset-root", default="commercial_dataset")
    parser.add_argument("--output-root", default="reviewed_training_dataset")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not 0 < args.val_ratio < 1:
        raise SystemExit("--val-ratio must be between 0 and 1")
    build(Path(args.dataset_root), Path(args.output_root), args.val_ratio, args.seed)


if __name__ == "__main__":
    main()