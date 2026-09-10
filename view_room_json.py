"""Simple viewer for floorplan room JSON results.

Usage:
    python view_room_json.py --json inference_output\\sample_page_1_rooms.json
"""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def draw_rooms_on_image(json_path: Path, output_path: Path):
    with open(json_path, 'r', encoding='utf-8') as f:
        payload = json.load(f)

    source_name = payload.get('source', json_path.stem)
    rooms = payload.get('rooms', [])

    image_path = json_path.with_name(f"{source_name}_original.png")
    if not image_path.exists():
        raise FileNotFoundError(f"Original image not found for {json_path}: {image_path}")

    img = cv2.imread(str(image_path))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    for room in rooms:
        polygon = np.array(room.get('polygon', []), dtype=np.int32)
        if polygon.size == 0:
            continue
        cv2.polylines(img, [polygon], True, (0, 0, 255), 2)
        center = room.get('center_point', [0, 0])
        if center:
            cv2.circle(img, (int(center[0]), int(center[1])), 4, (0, 255, 0), -1)
        label = room.get('room_label', f"room_{room.get('id', '')}")
        x, y = room['polygon'][0]
        cv2.putText(img, label, (x + 6, y + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(output_path)
    print(f"Saved visualized output to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Draw room polygons from a saved room JSON onto the original image.'
    )
    parser.add_argument('--json', required=True, help='Path to a rooms JSON file')
    parser.add_argument('--output', default='room_view.png', help='Output image path')
    args = parser.parse_args()

    draw_rooms_on_image(Path(args.json), Path(args.output))


if __name__ == '__main__':
    main()
