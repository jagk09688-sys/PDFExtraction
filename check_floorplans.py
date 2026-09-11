from pathlib import Path
import io
import json
import math
import cv2
from PIL import Image
import pymupdf

from app import detect_rooms, Config

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / 'Dataset'
OUTPUT_DIR = BASE_DIR / 'dataset_measurements'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

roll_widths = [3.66, 4.0]


def pdf_to_images(pdf_bytes: bytes, dpi: int = 200):
    doc = pymupdf.open(stream=pdf_bytes, filetype='pdf')
    images = []
    zoom = dpi / 72.0
    for page_num in range(len(doc)):
        page = doc[page_num]
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_data = pix.tobytes('ppm')
        img = Image.open(io.BytesIO(img_data)).convert('RGB')
        images.append(img)
    doc.close()
    return images


def room_dimensions_from_contour(room):
    contour = room['contour']
    try:
        rect = cv2.minAreaRect(contour)
        (_, _), (w_px, h_px), _ = rect
        length_px = max(w_px, h_px)
        width_px = min(w_px, h_px)
    except Exception:
        xs = [p[0] for p in room['polygon']]
        ys = [p[1] for p in room['polygon']]
        length_px = max(xs) - min(xs)
        width_px = max(ys) - min(ys)
    return length_px, width_px


def compute_carpet_for_room(length_m: float, width_m: float, roll_width_m: float):
    strips_a = max(1, math.ceil(width_m / roll_width_m)) if roll_width_m > 0 else 0
    strip_len_a = length_m
    total_len_a = strips_a * strip_len_a

    strips_b = max(1, math.ceil(length_m / roll_width_m)) if roll_width_m > 0 else 0
    strip_len_b = width_m
    total_len_b = strips_b * strip_len_b

    if total_len_a <= total_len_b:
        return {
            'roll_width_m': round(roll_width_m, 2),
            'selected_orientation': 'A',
            'strips': strips_a,
            'strip_length_m': round(strip_len_a, 3),
            'carpet_required_m': round(total_len_a, 3),
            'seams': max(0, strips_a - 1),
        }

    return {
        'roll_width_m': round(roll_width_m, 2),
        'selected_orientation': 'B',
        'strips': strips_b,
        'strip_length_m': round(strip_len_b, 3),
        'carpet_required_m': round(total_len_b, 3),
        'seams': max(0, strips_b - 1),
    }


def derive_room_category(length_m: float, width_m: float, area_m2: float):
    """Split the carpetable areas into living areas and other carpet areas."""
    if area_m2 <= 0:
        return 'carpet_area_room'

    min_dim = min(length_m, width_m)
    max_dim = max(length_m, width_m)

    if area_m2 >= 12.0 and min_dim >= 1.2 and max_dim >= 2.0:
        return 'living_area'

    return 'carpet_area_room'


all_file_summaries = []

for pdf in sorted(DATASET_DIR.glob('*.pdf')):
    pdf_bytes = pdf.read_bytes()
    images = pdf_to_images(pdf_bytes, dpi=Config.PDF_DPI)

    pages = []
    total_rooms = 0
    total_room_area_m2 = 0.0

    for page_num, pil_img in enumerate(images, start=1):
        _, rooms = detect_rooms(pil_img, min_area_px=Config.MIN_ROOM_AREA_PX)
        page_rooms = []
        page_total_area_m2 = 0.0

        for room_idx, room in enumerate(rooms, start=1):
            length_px, width_px = room_dimensions_from_contour(room)
            area_px = float(room['area_px'])
            ppm = Config.DEFAULT_PPM
            area_m2 = area_px / (ppm ** 2)
            length_m = length_px / ppm
            width_m = width_px / ppm
            room_category = derive_room_category(length_m, width_m, area_m2)

            if room_category not in {'living_area', 'carpet_area_room'}:
                continue

            room_entry = {
                'id': room_idx,
                'area_px': int(area_px),
                'area_m2': round(area_m2, 3),
                'length_m': round(length_m, 3),
                'width_m': round(width_m, 3),
                'room_category': room_category,
                'is_living_area': room_category == 'living_area',
                'polygon': [[int(p[0]), int(p[1])] for p in room['polygon']],
            }

            for roll_width in roll_widths:
                carpet = compute_carpet_for_room(length_m, width_m, roll_width)
                room_entry[f'carpet_{str(roll_width).replace(".", "_")}_m'] = carpet['carpet_required_m']
                room_entry[f'carpet_{str(roll_width).replace(".", "_")}_strips'] = carpet['strips']
                room_entry[f'carpet_{str(roll_width).replace(".", "_")}_seams'] = carpet['seams']

            page_rooms.append(room_entry)
            page_total_area_m2 += area_m2
            total_room_area_m2 += area_m2
            total_rooms += 1

        page_summary = {
            'page': page_num,
            'room_count': len(page_rooms),
            'total_area_m2': round(page_total_area_m2, 3),
            'rooms': page_rooms,
        }
        pages.append(page_summary)

    carpet_area_room_count = sum(1 for page in pages for room in page['rooms'] if room['room_category'] == 'carpet_area_room')
    living_area_room_count = sum(1 for page in pages for room in page['rooms'] if room['room_category'] == 'living_area')

    file_summary = {
        'pdf': pdf.name,
        'page_count': len(pages),
        'room_count': total_rooms,
        'total_area_m2': round(total_room_area_m2, 3),
        'carpet_area_room_count': carpet_area_room_count,
        'living_area_room_count': living_area_room_count,
        'pages': pages,
    }
    all_file_summaries.append(file_summary)

    with open(OUTPUT_DIR / f'{pdf.stem}_measurements.json', 'w', encoding='utf-8') as f:
        json.dump(file_summary, f, indent=2)

summary_payload = {
    'roll_widths_m': roll_widths,
    'total_room_count': sum(item['room_count'] for item in all_file_summaries),
    'total_area_m2': round(sum(item['total_area_m2'] for item in all_file_summaries), 3),
    'total_carpet_area_room_count': sum(item['carpet_area_room_count'] for item in all_file_summaries),
    'total_living_area_room_count': sum(item['living_area_room_count'] for item in all_file_summaries),
    'files': all_file_summaries,
}

with open(OUTPUT_DIR / 'floorplan_measurements_summary.json', 'w', encoding='utf-8') as f:
    json.dump(summary_payload, f, indent=2)

for roll_width in roll_widths:
    carpet_rows = []
    total_carpet_required_m = 0.0
    total_selected_area_m2 = 0.0
    total_rooms = 0

    for file_summary in all_file_summaries:
        for page in file_summary['pages']:
            for room in page['rooms']:
                carpet_key = f'carpet_{str(roll_width).replace(".", "_")}_m'
                carpet_required = room.get(carpet_key, 0)
                total_carpet_required_m += carpet_required
                total_selected_area_m2 += room['area_m2']
                total_rooms += 1

                carpet_rows.append({
                    'pdf': file_summary['pdf'],
                    'page': page['page'],
                    'room_id': room['id'],
                    'room_category': room['room_category'],
                    'is_living_area': room['is_living_area'],
                    'area_m2': room['area_m2'],
                    'length_m': room['length_m'],
                    'width_m': room['width_m'],
                    'carpet_required_m': carpet_required,
                })

    roll_summary = {
        'roll_width_m': round(roll_width, 2),
        'room_count': total_rooms,
        'total_selected_area_m2': round(total_selected_area_m2, 3),
        'total_carpet_required_m': round(total_carpet_required_m, 3),
        'rooms': carpet_rows,
    }

    with open(OUTPUT_DIR / f'carpet_summary_{roll_width}.json', 'w', encoding='utf-8') as f:
        json.dump(roll_summary, f, indent=2)

print(json.dumps({
    'output_dir': str(OUTPUT_DIR),
    'pdf_count': len(all_file_summaries),
    'total_room_count': sum(file_summary['room_count'] for file_summary in all_file_summaries),
    'total_room_area_m2': round(sum(file_summary['total_area_m2'] for file_summary in all_file_summaries), 3),
    'files': [str(p.name) for p in sorted(OUTPUT_DIR.glob('*'))],
}, indent=2))
