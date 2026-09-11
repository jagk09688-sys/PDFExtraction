"""Generate pseudo-label masks from existing floorplan images using the project's heuristic detector.

This is a practical intermediate step when no annotation JSON files are available yet.
It uses the contour-based room detector already present in app.py and writes binary masks
for each image in the given dataset folder.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from app import detect_rooms


def generate_masks(images_dir: Path, masks_dir: Path, min_area_px: int = 2000):
    images_dir = images_dir.resolve()
    masks_dir = masks_dir.resolve()
    masks_dir.mkdir(parents=True, exist_ok=True)

    image_paths = sorted(images_dir.glob('*.png'))
    if not image_paths:
        raise FileNotFoundError(f'No PNG images found in: {images_dir}')

    generated = 0
    for image_path in image_paths:
        pil_img = Image.open(image_path).convert('RGB')
        _, rooms = detect_rooms(pil_img, min_area_px=min_area_px)

        mask = np.zeros((pil_img.height, pil_img.width), dtype=np.uint8)
        for room in rooms:
            polygon = np.array(room.get('polygon', []), dtype=np.int32)
            if polygon.size == 0:
                continue
            cv2.fillPoly(mask, [polygon], 255)

        out_path = masks_dir / f'{image_path.stem}.png'
        cv2.imwrite(str(out_path), mask)
        generated += 1

    return generated


def main():
    parser = argparse.ArgumentParser(
        description='Generate heuristic room masks for floorplan images using the existing contour detector.'
    )
    parser.add_argument('--images-dir', required=True, help='Folder containing PNG images')
    parser.add_argument('--output-dir', required=True, help='Folder to write generated masks')
    parser.add_argument('--min-area-px', type=int, default=2000, help='Minimum contour area threshold (default: 2000)')
    args = parser.parse_args()

    generated = generate_masks(
        images_dir=Path(args.images_dir),
        masks_dir=Path(args.output_dir),
        min_area_px=args.min_area_px,
    )

    print(f'Generated {generated} heuristic masks at {args.output_dir}')


if __name__ == '__main__':
    main()
