"""Summarize inferred room JSON outputs into carpet installation estimates.

This script reads the per-room JSON files produced by infer_floorplan_segmentation.py
and calculates:
- room width/height in meters from the saved bbox
- room area in square meters
- total carpet required including a configurable waste allowance
- estimated number of carpet pieces / cuts (one piece per room)

Usage:
    python carpet_requirements.py --input-dir inference_output --waste-factor 0.10
"""

import argparse
import csv
import json
import math
from pathlib import Path


def load_json(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_room_area_m2(room: dict, default_pixels_per_meter: float = 100.0):
    if room.get('area_m2') is not None:
        return float(room['area_m2'])

    area_px = float(room.get('area_px', 0) or 0)
    pixels_per_meter = float(room.get('pixels_per_meter', default_pixels_per_meter) or default_pixels_per_meter)
    if pixels_per_meter <= 0:
        return 0.0
    return area_px / (pixels_per_meter ** 2)


def derive_pdf_name(source_name: str):
    if '_page_' in source_name:
        return source_name.rsplit('_page_', 1)[0]
    if '_page' in source_name:
        page_index = source_name.rfind('_page')
        return source_name[:page_index]
    return source_name


def write_csv_summary(summary: dict, output_path: Path):
    csv_path = output_path.with_suffix('.csv')

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'pdf_name', 'page_source', 'room_label', 'room_id', 'area_m2', 'width_m', 'height_m',
            'carpet_required_m2', 'estimated_cut_pieces', 'estimated_roll_lengths_used_m',
            'estimated_rolls_needed', 'waste_area_m2', 'usable_leftover_m2', 'reused_from_leftover',
            'reused_leftover_area_m2', 'roll_width_m', 'roll_length_m', 'estimated_cost_m2'
        ])

        for pdf in summary.get('pdfs', []):
            for page in pdf.get('pages', []):
                for room in page.get('rooms', []):
                    writer.writerow([
                        pdf.get('pdf_name', ''),
                        page.get('source', ''),
                        room.get('room_label', ''),
                        room.get('id', ''),
                        room.get('area_m2', ''),
                        room.get('width_m', ''),
                        room.get('height_m', ''),
                        room.get('carpet_required_m2', ''),
                        room.get('estimated_cut_pieces', ''),
                        room.get('estimated_roll_lengths_used_m', ''),
                        room.get('estimated_rolls_needed', ''),
                        room.get('waste_area_m2', ''),
                        room.get('usable_leftover_m2', ''),
                        room.get('reused_from_leftover', ''),
                        room.get('reused_leftover_area_m2', ''),
                        summary.get('roll_width_m', ''),
                        summary.get('roll_length_m', ''),
                        summary.get('price_per_m2', ''),
                    ])

    print(f'CSV summary saved: {csv_path}')


def write_pdf_totals_csv(summary: dict, output_path: Path):
    pdf_totals_path = output_path.with_name(f'{output_path.stem}_pdf_totals.csv')

    with open(pdf_totals_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'pdf_name', 'room_count', 'total_area_m2', 'carpet_required_m2', 'estimated_cut_pieces',
            'estimated_roll_lengths_used_m', 'estimated_rolls_needed', 'estimated_total_cost',
            'waste_area_m2', 'reused_leftover_area_m2', 'remaining_leftover_area_m2',
            'remaining_leftover_inventory', 'roll_width_m', 'roll_length_m', 'price_per_m2'
        ])

        for pdf in summary.get('pdfs', []):
            remaining_leftover_inventory = '; '.join(
                f"{item.get('width_m', 0):.4f}x{item.get('length_m', 0):.4f}m"
                for item in pdf.get('remaining_leftover_inventory', [])
            )
            writer.writerow([
                pdf.get('pdf_name', ''),
                pdf.get('room_count', ''),
                pdf.get('total_area_m2', ''),
                pdf.get('carpet_required_m2', ''),
                pdf.get('estimated_cut_pieces', ''),
                pdf.get('estimated_roll_lengths_used_m', ''),
                pdf.get('estimated_rolls_needed', ''),
                pdf.get('estimated_total_cost', ''),
                pdf.get('waste_area_m2', ''),
                pdf.get('reused_leftover_area_m2', ''),
                pdf.get('remaining_leftover_area_m2', ''),
                remaining_leftover_inventory,
                summary.get('roll_width_m', ''),
                summary.get('roll_length_m', ''),
                summary.get('price_per_m2', ''),
            ])

    print(f'PDF totals CSV saved: {pdf_totals_path}')


def plan_room_cuts(width_m: float, height_m: float, roll_width_m: float, roll_length_m: float):
    width_m = max(0.0, float(width_m))
    height_m = max(0.0, float(height_m))
    roll_width_m = max(0.0, float(roll_width_m))
    roll_length_m = max(0.0, float(roll_length_m))

    if width_m <= 0 or height_m <= 0 or roll_width_m <= 0:
        return {
            'pieces_needed': 0,
            'pieces': [],
            'roll_length_used_m': 0.0,
            'full_rolls_needed': 0,
            'waste_area_m2': 0.0,
            'usable_leftover_m2': 0.0,
            'remainder_width_m': 0.0,
        }

    pieces = []
    remaining_width = width_m
    piece_index = 1

    while remaining_width > 0:
        piece_width = min(roll_width_m, remaining_width)
        pieces.append({
            'piece_index': piece_index,
            'piece_width_m': round(piece_width, 4),
            'piece_length_m': round(height_m, 4),
            'piece_area_m2': round(piece_width * height_m, 4),
        })
        remaining_width -= piece_width
        piece_index += 1

    pieces_needed = len(pieces)
    total_roll_length_m = pieces_needed * height_m
    full_rolls_needed = math.ceil(total_roll_length_m / roll_length_m) if roll_length_m > 0 else pieces_needed

    remainder_width = width_m % roll_width_m if roll_width_m > 0 else 0.0
    usable_leftover_area_m2 = remainder_width * height_m if remainder_width > 0 else 0.0

    return {
        'pieces_needed': pieces_needed,
        'pieces': pieces,
        'roll_length_used_m': round(total_roll_length_m, 4),
        'full_rolls_needed': full_rolls_needed,
        'waste_area_m2': 0.0,
        'usable_leftover_m2': round(usable_leftover_area_m2, 4),
        'remainder_width_m': round(remainder_width, 4),
    }


def find_matching_leftover(leftover_inventory: list, room_width_m: float, room_height_m: float):
    for index, leftover in enumerate(leftover_inventory):
        if leftover.get('width_m', 0) >= room_width_m and leftover.get('length_m', 0) >= room_height_m:
            return index
    return None


def sort_leftover_inventory(leftover_inventory: list):
    sorted_items = []
    for item in leftover_inventory:
        width_m = float(item.get('width_m', 0) or 0)
        length_m = float(item.get('length_m', 0) or 0)
        if width_m > 0 and length_m > 0:
            sorted_items.append({'width_m': round(width_m, 4), 'length_m': round(length_m, 4)})
    sorted_items.sort(key=lambda item: (-item['length_m'], -item['width_m']))
    return sorted_items


def merge_leftover_inventory(leftover_inventory: list, roll_width_m: float):
    if not leftover_inventory:
        return []

    merged = []
    for item in sort_leftover_inventory(leftover_inventory):
        matched = False
        for existing in merged:
            if abs(existing['length_m'] - item['length_m']) <= 1e-4:
                existing['width_m'] = round(existing['width_m'] + item['width_m'], 4)
                matched = True
                break
        if not matched:
            merged.append({'width_m': round(item['width_m'], 4), 'length_m': round(item['length_m'], 4)})

    simplified = []
    for item in merged:
        width_m = float(item.get('width_m', 0) or 0)
        length_m = float(item.get('length_m', 0) or 0)
        while width_m > roll_width_m + 1e-4:
            simplified.append({'width_m': round(roll_width_m, 4), 'length_m': round(length_m, 4)})
            width_m = round(width_m - roll_width_m, 4)
        if width_m > 1e-4:
            simplified.append({'width_m': round(width_m, 4), 'length_m': round(length_m, 4)})

    return sort_leftover_inventory(simplified)


def summarize_directory(input_dir: Path, waste_factor: float, roll_width_m: float, roll_length_m: float, price_per_m2: float):
    room_files = sorted(input_dir.rglob('*_rooms.json'))
    if not room_files:
        raise FileNotFoundError(f'No *_rooms.json files found under: {input_dir}')

    roll_area_m2 = float(roll_width_m) * float(roll_length_m)
    if roll_area_m2 <= 0:
        raise ValueError('Roll area must be greater than zero. Check roll width and roll length.')

    total_reused_leftover_m2 = 0.0
    total_rooms = 0
    total_carpet_required_m2 = 0.0
    total_cut_pieces = 0
    total_roll_lengths_used_m = 0.0
    total_waste_area_m2 = 0.0
    pdf_summaries = {}

    for json_path in room_files:
        payload = load_json(json_path)
        rooms = payload.get('rooms', [])
        if not rooms:
            continue

        pdf_leftover_inventory = []
        pdf_reused_leftover_area_m2 = 0.0

        source_name = payload.get('source', json_path.stem)
        pdf_name = derive_pdf_name(source_name)

        if pdf_name not in pdf_summaries:
            pdf_summaries[pdf_name] = {
                'pdf_name': pdf_name,
                'room_count': 0,
                'pages': [],
                'total_area_m2': 0.0,
                'carpet_required_m2': 0.0,
                'estimated_cut_pieces': 0,
                'estimated_roll_lengths_used_m': 0.0,
                'waste_area_m2': 0.0,
                'reused_leftover_area_m2': 0.0,
            }

        page_summary = {
            'source': source_name,
            'room_count': len(rooms),
            'rooms': [],
            'total_area_m2': 0.0,
            'carpet_required_m2': 0.0,
            'estimated_cut_pieces': 0,
            'estimated_roll_lengths_used_m': 0.0,
            'waste_area_m2': 0.0,
            'reused_leftover_area_m2': 0.0,
        }

        for room in rooms:
            bbox = room.get('bbox', [0, 0, 0, 0])
            x1, y1, x2, y2 = bbox[:4]
            width_px = max(0, x2 - x1)
            height_px = max(0, y2 - y1)

            image_resolution = payload.get('image_resolution', [0, 0])
            pixels_per_meter = 100.0
            if image_resolution and image_resolution[0] > 0:
                pixels_per_meter = max(1.0, image_resolution[0] / max(1, int(image_resolution[1] or 1)))

            width_m = width_px / pixels_per_meter
            height_m = height_px / pixels_per_meter
            area_m2 = get_room_area_m2(room, pixels_per_meter)
            required_m2 = area_m2 * (1 + waste_factor)

            leftover_index = find_matching_leftover(pdf_leftover_inventory, width_m, height_m)
            reused_leftover_area_m2 = 0.0
            cut_plan = None

            if leftover_index is not None:
                leftover = pdf_leftover_inventory[leftover_index]
                reused_leftover_area_m2 = width_m * height_m
                leftover['width_m'] = max(0.0, leftover['width_m'] - width_m)
                leftover['length_m'] = max(0.0, leftover['length_m'] - height_m)
                if leftover['width_m'] <= 0.0001 and leftover['length_m'] <= 0.0001:
                    pdf_leftover_inventory.pop(leftover_index)
                elif leftover['width_m'] <= 0.0001 or leftover['length_m'] <= 0.0001:
                    pdf_leftover_inventory[leftover_index] = {
                        'width_m': max(0.0, leftover['width_m']),
                        'length_m': max(0.0, leftover['length_m']),
                    }

                cut_plan = {
                    'pieces_needed': 0,
                    'pieces': [],
                    'roll_length_used_m': 0.0,
                    'full_rolls_needed': 0,
                    'waste_area_m2': 0.0,
                    'usable_leftover_m2': 0.0,
                    'remainder_width_m': 0.0,
                }
            else:
                cut_plan = plan_room_cuts(width_m, height_m, roll_width_m, roll_length_m)
                if cut_plan['remainder_width_m'] > 0.0001:
                    pdf_leftover_inventory.append({
                        'width_m': round(cut_plan['remainder_width_m'], 4),
                        'length_m': round(height_m, 4),
                    })

            pdf_leftover_inventory = merge_leftover_inventory(pdf_leftover_inventory, roll_width_m)

            room_entry = {
                'room_label': room.get('room_label', ''),
                'id': room.get('id', ''),
                'area_m2': round(area_m2, 4),
                'width_m': round(width_m, 4),
                'height_m': round(height_m, 4),
                'carpet_required_m2': round(required_m2, 4),
                'estimated_cut_pieces': cut_plan['pieces_needed'],
                'estimated_roll_lengths_used_m': cut_plan['roll_length_used_m'],
                'estimated_rolls_needed': cut_plan['full_rolls_needed'],
                'estimated_full_rolls_needed': cut_plan['full_rolls_needed'],
                'waste_area_m2': cut_plan['waste_area_m2'],
                'usable_leftover_m2': cut_plan['usable_leftover_m2'],
                'reused_from_leftover': leftover_index is not None,
                'reused_leftover_area_m2': round(reused_leftover_area_m2, 4),
                'cut_plan': cut_plan['pieces'],
            }
            page_summary['rooms'].append(room_entry)
            page_summary['total_area_m2'] += area_m2
            page_summary['carpet_required_m2'] += required_m2
            page_summary['estimated_cut_pieces'] += cut_plan['pieces_needed']
            page_summary['estimated_roll_lengths_used_m'] += cut_plan['roll_length_used_m']
            page_summary['waste_area_m2'] += cut_plan['waste_area_m2']
            page_summary['reused_leftover_area_m2'] = page_summary.get('reused_leftover_area_m2', 0.0) + reused_leftover_area_m2
            total_reused_leftover_m2 += reused_leftover_area_m2

        page_summary['total_area_m2'] = round(page_summary['total_area_m2'], 4)
        page_summary['carpet_required_m2'] = round(page_summary['carpet_required_m2'], 4)
        page_summary['room_count'] = len(page_summary['rooms'])

        pdf_remaining_leftover_inventory = merge_leftover_inventory(pdf_leftover_inventory, roll_width_m)
        pdf_remaining_leftover_area_m2 = round(sum(
            float(item.get('width_m', 0) or 0) * float(item.get('length_m', 0) or 0)
            for item in pdf_remaining_leftover_inventory
        ), 4)

        pdf_summaries[pdf_name]['pages'].append(page_summary)
        pdf_summaries[pdf_name]['room_count'] += len(page_summary['rooms'])
        pdf_summaries[pdf_name]['total_area_m2'] += page_summary['total_area_m2']
        pdf_summaries[pdf_name]['carpet_required_m2'] += page_summary['carpet_required_m2']
        pdf_summaries[pdf_name]['estimated_cut_pieces'] += page_summary['estimated_cut_pieces']
        pdf_summaries[pdf_name]['estimated_roll_lengths_used_m'] += page_summary['estimated_roll_lengths_used_m']
        pdf_summaries[pdf_name]['waste_area_m2'] += page_summary['waste_area_m2']
        pdf_summaries[pdf_name]['reused_leftover_area_m2'] += page_summary.get('reused_leftover_area_m2', 0.0)
        pdf_summaries[pdf_name]['remaining_leftover_area_m2'] = pdf_remaining_leftover_area_m2
        pdf_summaries[pdf_name]['remaining_leftover_inventory'] = [
            {
                'width_m': round(float(item.get('width_m', 0) or 0), 4),
                'length_m': round(float(item.get('length_m', 0) or 0), 4),
            }
            for item in pdf_remaining_leftover_inventory
        ]

        total_rooms += len(rooms)
        total_carpet_required_m2 += page_summary['carpet_required_m2']
        total_cut_pieces += page_summary['estimated_cut_pieces']
        total_roll_lengths_used_m += page_summary['estimated_roll_lengths_used_m']
        total_waste_area_m2 += page_summary['waste_area_m2']

    pdf_list = []
    for pdf_name, summary in pdf_summaries.items():
        summary['total_area_m2'] = round(summary['total_area_m2'], 4)
        summary['carpet_required_m2'] = round(summary['carpet_required_m2'], 4)
        summary['estimated_roll_lengths_used_m'] = round(summary['estimated_roll_lengths_used_m'], 4)
        summary['waste_area_m2'] = round(summary['waste_area_m2'], 4)
        summary['estimated_rolls_needed'] = math.ceil(summary['estimated_roll_lengths_used_m'] / roll_length_m) if roll_length_m > 0 else summary['estimated_cut_pieces']
        summary['estimated_full_rolls_needed'] = summary['estimated_rolls_needed']
        summary['estimated_total_cost'] = round(summary['carpet_required_m2'] * price_per_m2, 4)
        summary['reused_leftover_area_m2'] = round(summary.get('reused_leftover_area_m2', 0.0), 4)
        summary['remaining_leftover_area_m2'] = round(summary.get('remaining_leftover_area_m2', 0.0), 4)
        summary['remaining_leftover_inventory'] = summary.get('remaining_leftover_inventory', [])
        pdf_list.append(summary)

    total_rolls_needed = math.ceil(total_roll_lengths_used_m / roll_length_m) if roll_length_m > 0 else total_cut_pieces
    total_full_rolls_needed = total_rolls_needed
    total_cost = round(total_carpet_required_m2 * price_per_m2, 4)

    summary = {
        'input_dir': str(input_dir),
        'waste_factor': waste_factor,
        'roll_width_m': roll_width_m,
        'roll_length_m': roll_length_m,
        'area_per_roll_m2': round(roll_area_m2, 4),
        'price_per_m2': price_per_m2,
        'room_files_processed': len(room_files),
        'total_rooms': total_rooms,
        'total_carpet_required_m2': round(total_carpet_required_m2, 4),
        'estimated_total_cut_pieces': total_cut_pieces,
        'estimated_total_roll_lengths_used_m': round(total_roll_lengths_used_m, 4),
        'estimated_total_rolls': total_rolls_needed,
        'estimated_total_full_rolls': total_full_rolls_needed,
        'estimated_total_cost': total_cost,
        'estimated_total_waste_area_m2': round(total_waste_area_m2, 4),
        'total_reused_leftover_m2': round(total_reused_leftover_m2, 4),
        'leftover_inventory': [],
        'pdfs': sorted(pdf_list, key=lambda item: item['pdf_name']),
        'pages': sorted(
            [
                {**page, 'pdf_name': derive_pdf_name(page['source'])}
                for pdf in pdf_list
                for page in pdf['pages']
            ],
            key=lambda item: (item['pdf_name'], item['source'])
        ),
    }

    return summary


def main():
    parser = argparse.ArgumentParser(
        description='Summarize room JSON files into carpet installation estimates.'
    )
    parser.add_argument('--input-dir', required=True, help='Directory containing *_rooms.json outputs')
    parser.add_argument('--waste-factor', type=float, default=0.10, help='Extra carpet allowance factor (default: 0.10 = 10%)')
    parser.add_argument('--roll-width-m', type=float, default=4.0, help='Roll width in meters used for estimating rolls (default: 4.0)')
    parser.add_argument('--roll-length-m', type=float, default=25.0, help='Roll length in meters used for estimating rolls (default: 25.0)')
    parser.add_argument('--price-per-m2', type=float, default=0.0, help='Optional carpet price per square meter for cost estimates (default: 0.0)')
    parser.add_argument('--output', default='carpet_requirements_summary.json', help='Output summary JSON file')
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f'Input directory not found: {input_dir}')

    summary = summarize_directory(input_dir, args.waste_factor, args.roll_width_m, args.roll_length_m, args.price_per_m2)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    write_csv_summary(summary, output_path)
    write_pdf_totals_csv(summary, output_path)

    print(json.dumps({
        'total_rooms': summary['total_rooms'],
        'total_carpet_required_m2': summary['total_carpet_required_m2'],
        'estimated_total_cut_pieces': summary['estimated_total_cut_pieces'],
        'estimated_total_rolls': summary['estimated_total_rolls'],
        'estimated_total_cost': summary['estimated_total_cost'],
        'summary_path': str(output_path),
    }, indent=2))


if __name__ == '__main__':
    main()
