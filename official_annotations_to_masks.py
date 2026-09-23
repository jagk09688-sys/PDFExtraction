"""Create binary room masks from official page annotation JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def write_mask(annotation_path: Path, output_dir: Path) -> Path:
    data = json.loads(annotation_path.read_text(encoding="utf-8"))
    mask = np.zeros((int(data["image_height"]), int(data["image_width"])), dtype=np.uint8)
    for room in data.get("rooms", []):
        polygon = np.asarray(room["polygon"], dtype=np.int32)
        if len(polygon) >= 3:
            cv2.fillPoly(mask, [polygon], 255)
    output_path = output_dir / f"{annotation_path.stem}.png"
    if not cv2.imwrite(str(output_path), mask):
        raise RuntimeError(f"Could not write {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export room masks from official page annotations.")
    parser.add_argument("annotations_dir")
    parser.add_argument("output_dir")
    args = parser.parse_args()
    annotation_dir = Path(args.annotations_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(annotation_dir.glob("page_*.json"))
    if not paths:
        raise SystemExit("No page_*.json files found")
    for path in paths:
        print(f"Wrote {write_mask(path, output_dir)}")


if __name__ == "__main__":
    main()