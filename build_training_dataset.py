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


def build(
    dataset_root: Path,
    output_root: Path,
    val_ratio: float,
    seed: int,
    allow_auto_drafts: bool = False,
    max_pseudo_rooms: int = 25,
) -> None:
    project_root = dataset_root / "projects"
    projects = sorted(path for path in project_root.iterdir() if path.is_dir())
    eligible = []
    pseudo_label_projects = 0
    report = {
        "projects": len(projects),
        "eligible_projects": 0,
        "eligible_pages": 0,
        "pseudo_label_projects": 0,
        "pseudo_label_pages": 0,
        "pseudo_label_rooms": 0,
        "excluded_pages": [],
        "skipped": [],
    }

    for project in projects:
        annotation_dirs = [project / "annotations"]
        if allow_auto_drafts:
            annotation_dirs.append(project / "annotation_drafts")

        page_stems = set()
        for annotation_dir in annotation_dirs:
            if annotation_dir.exists():
                page_stems.update(path.stem for path in annotation_dir.glob("page_*.json"))

        annotations = []
        problems = []
        for page_stem in sorted(page_stems):
            candidates = []
            for annotation_dir in annotation_dirs:
                if annotation_dir.exists():
                    candidate = annotation_dir / f"{page_stem}.json"
                    if candidate.exists():
                        candidates.append(candidate)
            candidates.sort(key=lambda path: 0 if path.parent.name == "annotations" else 1)
            selected = None
            page_problems = []
            for annotation in candidates:
                errors = validate_page(annotation)
                if errors:
                    page_problems.extend(errors)
                    continue
                data = json.loads(annotation.read_text(encoding="utf-8"))
                is_auto_draft = data.get("annotator") == "AUTO_DRAFT_REQUIRES_REVIEW"
                if is_auto_draft and not allow_auto_drafts:
                    page_problems.append(f"{annotation.name}: automatic draft is not eligible")
                    continue
                if not data.get("rooms"):
                    page_problems.append(f"{annotation.name}: no reviewed rooms")
                    continue
                if is_auto_draft and len(data["rooms"]) > max_pseudo_rooms:
                    page_problems.append(
                        f"{annotation.name}: {len(data['rooms'])} draft room candidates exceed the pseudo-label limit of {max_pseudo_rooms}"
                    )
                    continue
                selected = annotation
                break
            if selected is not None:
                annotations.append(selected)
            elif candidates:
                reasons = page_problems[:5] or [f"{page_stem}.json: no reviewed rooms"]
                problems.extend(reasons)
                report["excluded_pages"].append({"project": project.name, "page": page_stem, "reasons": reasons})
            else:
                problems.append(f"{page_stem}.json: no annotation file")

        valid = annotations[:]
        if valid:
            if any(json.loads(path.read_text(encoding="utf-8")).get("annotator") == "AUTO_DRAFT_REQUIRES_REVIEW" for path in valid):
                pseudo_label_projects += 1
            for path in valid:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("annotator") == "AUTO_DRAFT_REQUIRES_REVIEW":
                    report["pseudo_label_pages"] += 1
                    report["pseudo_label_rooms"] += len(data.get("rooms", []))
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
    report["pseudo_label_projects"] = pseudo_label_projects
    report["train_projects"] = len(eligible) - len(val_projects)
    report["val_projects"] = len(val_projects)
    report["train_pages"] = len(list((output_root / "train" / "images").glob("*.png")))
    report["val_pages"] = len(list((output_root / "val" / "images").glob("*.png")))
    if allow_auto_drafts:
        report["warning"] = "Using auto-generated draft rooms as pseudo-labels for early training; review before production use."
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
    parser.add_argument("--allow-auto-drafts", action="store_true", help="Allow AUTO_DRAFT_REQUIRES_REVIEW page annotations as pseudo-labels for early training.")
    parser.add_argument("--max-pseudo-rooms", type=int, default=25, help="Skip auto-draft pages with more room candidates than this, as likely noisy detections.")
    args = parser.parse_args()
    if not 0 < args.val_ratio < 1:
        raise SystemExit("--val-ratio must be between 0 and 1")
    if args.max_pseudo_rooms < 1:
        raise SystemExit("--max-pseudo-rooms must be at least 1")
    build(
        Path(args.dataset_root),
        Path(args.output_root),
        args.val_ratio,
        args.seed,
        allow_auto_drafts=args.allow_auto_drafts,
        max_pseudo_rooms=args.max_pseudo_rooms,
    )


if __name__ == "__main__":
    main()