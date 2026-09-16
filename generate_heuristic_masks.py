"""Generate pseudo-label masks from existing floorplan images using the project's heuristic detector.

This is a practical intermediate step when no annotation JSON files are available yet.
It uses the contour-based room detector already present in app.py and writes binary masks
for each image in the given dataset folder.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from app import detect_rooms


def generate_masks(images_dir: Path, masks_dir: Path, min_area_px: int = 2000, max_rooms: int = 25, force: bool = False):
    images_dir = images_dir.resolve()
    masks_dir = masks_dir.resolve()
    masks_dir.mkdir(parents=True, exist_ok=True)

    image_paths = sorted(images_dir.glob('*.png'))
    if not image_paths:
        raise FileNotFoundError(f'No PNG images found in: {images_dir}')

    generated = 0
    report = []
    for image_path in image_paths:
        Image.MAX_IMAGE_PIXELS = None
        pil_img = Image.open(image_path).convert('RGB')
        _, rooms = detect_rooms(pil_img, min_area_px=min_area_px)

        reliable = 0 < len(rooms) <= max_rooms
        entry = {
            'image': image_path.name,
            'detected_candidates': len(rooms),
            'positive_pixels': 0,
            'reliable_for_training': reliable,
            'reason': 'ok' if reliable else f'detected {len(rooms)} candidates; expected at most {max_rooms}',
        }

        mask = np.zeros((pil_img.height, pil_img.width), dtype=np.uint8)
        if reliable or force:
            for room in rooms:
                polygon = np.array(room.get('polygon', []), dtype=np.int32)
                if polygon.size == 0:
                    continue
                cv2.fillPoly(mask, [polygon], 255)

            out_path = masks_dir / f'{image_path.stem}.png'
            cv2.imwrite(str(out_path), mask)
            generated += 1
            entry['positive_pixels'] = int(np.count_nonzero(mask))
        else:
            entry['reason'] += '; mask was not written'

        report.append(entry)

    report_path = masks_dir / 'heuristic_mask_quality.json'
    report_path.write_text(json.dumps({'images': report}, indent=2), encoding='utf-8')

    return generated, report_path


def main():
    parser = argparse.ArgumentParser(
        description='Generate heuristic room masks for floorplan images using the existing contour detector.'
    )
    parser.add_argument('--images-dir', required=True, help='Folder containing PNG images')
    parser.add_argument('--output-dir', required=True, help='Folder to write generated masks')
    parser.add_argument('--min-area-px', type=int, default=2000, help='Minimum contour area threshold (default: 2000)')
    parser.add_argument('--max-rooms', type=int, default=25, help='Maximum candidates accepted as a training mask (default: 25)')
    parser.add_argument('--force', action='store_true', help='Write rejected candidate masks for visual review; never use them for training without annotation review')
    args = parser.parse_args()

    generated, report_path = generate_masks(
        images_dir=Path(args.images_dir),
        masks_dir=Path(args.output_dir),
        min_area_px=args.min_area_px,
        max_rooms=args.max_rooms,
        force=args.force,
    )

    print(f'Generated {generated} heuristic masks at {args.output_dir}')
    print(f'Quality report: {report_path}')


if __name__ == '__main__':
    main()
