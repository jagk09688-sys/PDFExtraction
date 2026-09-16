import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np


def room_dimensions_from_points(points):
    pts = np.asarray(points, dtype=np.float32)
    if pts.shape[0] < 3:
        return None, None, 0.0

    rect = cv2.minAreaRect(pts)
    (_, _), (w_px, h_px), _ = rect
    length_px = max(float(w_px), float(h_px))
    width_px = min(float(w_px), float(h_px))
    area_px = float(cv2.contourArea(pts))
    return length_px, width_px, area_px


def calculate_carpet_requirement(length_m: float, width_m: float, roll_width_m: float):
    if length_m <= 0 or width_m <= 0 or roll_width_m <= 0:
        return {
            'selected_orientation': 'A',
            'strips': 0,
            'strip_length_m': 0.0,
            'carpet_required_m': 0.0,
            'seams': 0,
        }

    strips_a = max(1, math.ceil(width_m / roll_width_m))
    strip_len_a = length_m
    total_len_a = strips_a * strip_len_a

    strips_b = max(1, math.ceil(length_m / roll_width_m))
    strip_len_b = width_m
    total_len_b = strips_b * strip_len_b

    if total_len_a <= total_len_b:
        return {
            'selected_orientation': 'A',
            'strips': strips_a,
            'strip_length_m': round(strip_len_a, 3),
            'carpet_required_m': round(total_len_a, 3),
            'seams': max(0, strips_a - 1),
        }

    return {
        'selected_orientation': 'B',
        'strips': strips_b,
        'strip_length_m': round(strip_len_b, 3),
        'carpet_required_m': round(total_len_b, 3),
        'seams': max(0, strips_b - 1),
    }


def classify_material(room_name: str, carpet_labels=None, hardfloor_labels=None):
    carpet_labels = {x.strip().lower() for x in (carpet_labels or []) if x and x.strip()}
    hardfloor_labels = {x.strip().lower() for x in (hardfloor_labels or []) if x and x.strip()}
    name = room_name.strip().lower()

    if name in carpet_labels:
        return 'carpet'
    if name in hardfloor_labels:
        return 'hardflooring'

    # Default smart rule: larger, broader rooms are usually carpet; service/wet rooms are hardflooring.
    if any(token in name for token in ['bath', 'toilet', 'laundry', 'kitchen', 'utility', 'wet', 'balcony', 'store', 'stairs', 'service']):
        return 'hardflooring'
    return 'carpet'


def process_annotation_file(json_path: Path, pixels_per_meter: float | None = None, carpet_labels=None, hardfloor_labels=None):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    rooms = []
    for shape in data.get('shapes', []):
        points = shape.get('points')
        if not points or len(points) < 3:
            continue

        label = (shape.get('label') or shape.get('name') or 'room').strip()
        if not label:
            label = 'room'

        length_px, width_px, area_px = room_dimensions_from_points(points)
        if length_px is None or width_px is None:
            continue

        length_m = round(length_px / pixels_per_meter, 3) if pixels_per_meter and pixels_per_meter > 0 else None
        width_m = round(width_px / pixels_per_meter, 3) if pixels_per_meter and pixels_per_meter > 0 else None
        area_m2 = round(area_px / (pixels_per_meter ** 2), 3) if pixels_per_meter and pixels_per_meter > 0 else None
        material_type = classify_material(label, carpet_labels, hardfloor_labels)

        room_entry = {
            'room_name': label,
            'length_px': round(length_px, 2),
            'width_px': round(width_px, 2),
            'area_px': round(area_px, 2),
            'length_m': length_m,
            'width_m': width_m,
            'area_m2': area_m2,
            'material_type': material_type,
            'points': [[round(float(x), 2), round(float(y), 2)] for x, y in points],
        }

        for roll_width in [3.66, 4.0]:
            carpet = calculate_carpet_requirement(length_m or 0.0, width_m or 0.0, roll_width) if length_m is not None and width_m is not None else {'carpet_required_m': 0.0, 'strips': 0, 'seams': 0, 'selected_orientation': 'A'}
            room_entry[f'carpet_required_{str(roll_width).replace(".", "_")}_m'] = carpet['carpet_required_m'] if material_type == 'carpet' else 0.0
            room_entry[f'carpet_{str(roll_width).replace(".", "_")}_strips'] = carpet['strips'] if material_type == 'carpet' else 0
            room_entry[f'carpet_{str(roll_width).replace(".", "_")}_seams'] = carpet['seams'] if material_type == 'carpet' else 0

        room_entry['hardflooring_area_m2'] = area_m2 if material_type == 'hardflooring' else 0.0
        rooms.append(room_entry)

    return rooms


def summarize_materials(room_entries):
    carpet_rooms = [r for r in room_entries if r['material_type'] == 'carpet']
    hardfloor_rooms = [r for r in room_entries if r['material_type'] == 'hardflooring']
    summary = {
        'total_room_count': len(room_entries),
        'total_carpet_area_m2': round(sum(r['area_m2'] or 0.0 for r in carpet_rooms), 3),
        'total_hardflooring_area_m2': round(sum(r['area_m2'] or 0.0 for r in hardfloor_rooms), 3),
        'total_carpet_required_3_66_m': round(sum(r['carpet_required_3_66_m'] for r in room_entries), 3),
        'total_carpet_required_4_0_m': round(sum(r['carpet_required_4_0_m'] for r in room_entries), 3),
    }
    return summary


def main():
    p = argparse.ArgumentParser(description='Export room names, sizes, carpet roll usage, and hardflooring area from LabelMe JSON annotations.')
    p.add_argument('--annotations', required=True, help='Folder containing LabelMe JSON files')
    p.add_argument('--output', default='room_measurements', help='Folder to write per-file JSON outputs')
    p.add_argument('--pixels-per-meter', type=float, default=200.0, help='Pixels per meter for converting px to meters')
    p.add_argument('--carpet-labels', default='living_area,carpet_area_room,bedroom,living_room,dining,study,master_bedroom,guest_room', help='Comma-separated room labels treated as carpeted areas')
    p.add_argument('--hardfloor-labels', default='bathroom,toilet,laundry,kitchen,utility,wet_area,balcony,store,stairs,service', help='Comma-separated room labels treated as hardflooring areas')
    args = p.parse_args()

    annotations_dir = Path(args.annotations)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not annotations_dir.exists():
        raise FileNotFoundError(f'Annotations folder not found: {annotations_dir}')

    carpet_labels = [x.strip() for x in args.carpet_labels.split(',') if x.strip()]
    hardfloor_labels = [x.strip() for x in args.hardfloor_labels.split(',') if x.strip()]

    combined = []
    for json_path in sorted(annotations_dir.glob('*.json')):
        rooms = process_annotation_file(json_path, args.pixels_per_meter, carpet_labels, hardfloor_labels)
        if not rooms:
            continue

        file_payload = {
            'source_file': json_path.name,
            'room_count': len(rooms),
            'rooms': rooms,
            'summary': summarize_materials(rooms),
        }
        combined.extend(rooms)

        out_path = output_dir / f'{json_path.stem}_rooms.json'
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(file_payload, f, indent=2)

        print(f'Wrote {out_path} with {len(rooms)} rooms')

    all_path = output_dir / 'all_rooms.json'
    with open(all_path, 'w', encoding='utf-8') as f:
        json.dump({
            'room_count': len(combined),
            'summary': summarize_materials(combined),
            'rooms': combined,
        }, f, indent=2)

    print(f'Finished. Total extracted rooms: {len(combined)}')
    print(f'Combined output: {all_path}')


if __name__ == '__main__':
    main()
