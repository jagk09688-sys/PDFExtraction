"""Run a trained U-Net floorplan segmentation model on PDFs or images.

This script now performs the full pipeline:
1. Convert PDFs to images
2. Predict room masks with the trained U-Net
3. Extract room polygons from the predicted mask
4. Save cleaned room JSON results alongside images and mask outputs

Example:
    python infer_floorplan_segmentation.py --input sample.pdf --model model_best.pth --output-dir inference_output
"""

import argparse
import csv
import io
import json
import os
from pathlib import Path

import cv2
import numpy as np
import torch
import segmentation_models_pytorch as smp
from PIL import Image

try:
    import pymupdf
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None

try:
    from pdf2image import convert_from_bytes
except ImportError:
    convert_from_bytes = None


def resolve_model_path(model_path):
    if model_path is None:
        model_path = 'model_best.pth'
    if not os.path.isabs(model_path):
        model_path = os.path.join(os.getcwd(), model_path)
    return model_path


def convert_pdf_to_images(pdf_bytes: bytes, dpi: int = 200):
    """Convert a PDF to a list of PIL images."""
    if pymupdf is not None:
        try:
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
        except Exception:
            pass

    if convert_from_bytes is None:
        raise RuntimeError('Neither PyMuPDF nor pdf2image is available for PDF conversion.')

    images = convert_from_bytes(pdf_bytes, dpi=dpi)
    return [img.convert('RGB') for img in images]


def load_model(model_path: str, device):
    model = smp.Unet(
        encoder_name='resnet34',
        encoder_weights=None,
        in_channels=3,
        classes=1,
        activation=None,
    )

    state = torch.load(model_path, map_location=device)
    if isinstance(state, dict) and 'state_dict' in state:
        state_dict = state['state_dict']
    else:
        state_dict = state

    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    return model


def predict_mask_with_probs(model, pil_img, device, threshold=0.5):
    img = np.array(pil_img.convert('RGB'), dtype=np.float32) / 255.0
    inp = np.transpose(img, (2, 0, 1))[None, ...]
    tensor = torch.from_numpy(inp).to(device)

    with torch.no_grad():
        logits = model(tensor)
        probs = torch.sigmoid(logits)

    probs_np = probs[0, 0].cpu().numpy()
    mask = (probs_np >= threshold).astype(np.uint8) * 255
    return mask, probs_np


def predict_mask(model, pil_img, device, threshold=0.5):
    mask, _ = predict_mask_with_probs(model, pil_img, device, threshold=threshold)
    return mask


def clean_mask(mask: np.ndarray, min_area_px: int = 2000):
    """Clean a predicted segmentation mask by removing noise and small artifacts."""
    if mask is None:
        return np.zeros((0, 0), dtype=np.uint8)

    binary = (mask > 127).astype(np.uint8) * 255

    # Mild opening removes small noise, closing reconnects slightly broken regions.
    open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, open_kernel, iterations=1)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, close_kernel, iterations=1)

    # Keep only connected components that are large enough to be meaningful rooms.
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    cleaned = np.zeros_like(binary)

    for label in range(1, num_labels):
        area = stats[label, cv2.CC_STAT_AREA]
        if area >= min_area_px:
            cleaned[labels == label] = 255

    return cleaned


def extract_rooms_from_mask(mask: np.ndarray, min_area_px: int = 2000, probs: np.ndarray = None, pixels_per_meter: float = 100.0):
    """Convert a binary mask into cleaned room polygons with basic room metrics."""
    if mask is None:
        return []

    binary = clean_mask(mask, min_area_px=min_area_px)
    if binary.size == 0 or binary.max() == 0:
        return []

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rooms = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area_px:
            continue

        epsilon = max(0.001, 0.004) * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        if len(approx) < 3:
            continue

        polygon = [[int(point[0][0]), int(point[0][1])] for point in approx]
        x_coords = [point[0] for point in polygon]
        y_coords = [point[1] for point in polygon]
        bbox = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]

        perimeter_px = int(round(cv2.arcLength(contour, True)))
        m = cv2.moments(contour)
        if m['m00'] != 0:
            cx = int(round(m['m10'] / m['m00']))
            cy = int(round(m['m01'] / m['m00']))
        else:
            cx, cy = bbox[0], bbox[1]
        center_point = [cx, cy]

        room_mask = np.zeros_like(binary)
        cv2.drawContours(room_mask, [contour], -1, 255, thickness=-1)

        area_m2 = 0.0
        approx_area_m2 = 0.0
        confidence = 0.0
        density = 0.0
        if pixels_per_meter > 0:
            area_m2 = area / (pixels_per_meter ** 2)
            approx_area_m2 = area_m2

        if probs is not None and room_mask.size > 0:
            valid_probs = probs[room_mask > 0]
            if valid_probs.size > 0:
                confidence = float(valid_probs.mean())

        if perimeter_px > 0:
            density = float(area / perimeter_px) if perimeter_px > 0 else 0.0

        rooms.append(
            {
                'area_px': int(area),
                'area_m2': round(area_m2, 4),
                'approx_area_m2': round(approx_area_m2, 4),
                'confidence': round(confidence, 4),
                'density': round(density, 4),
                'perimeter_px': perimeter_px,
                'center_point': center_point,
                'polygon': polygon,
                'bbox': bbox,
            }
        )

    rooms = sorted(rooms, key=lambda item: item['area_px'], reverse=True)
    for room_idx, room in enumerate(rooms, start=1):
        room['id'] = room_idx
        room['room_label'] = f"room_{room_idx}"

    return rooms


def save_outputs(base_dir: Path, img: Image.Image, mask: np.ndarray, rooms: list, stem: str):
    base_dir.mkdir(parents=True, exist_ok=True)

    original_path = base_dir / f'{stem}_original.png'
    mask_path = base_dir / f'{stem}_mask.png'
    overlay_path = base_dir / f'{stem}_overlay.png'
    json_path = base_dir / f'{stem}_rooms.json'
    csv_path = base_dir / f'{stem}_rooms.csv'

    img.save(original_path)
    Image.fromarray(mask.astype(np.uint8)).save(mask_path)

    img_rgb = np.array(img.convert('RGB'))
    overlay = img_rgb.copy()
    for room in rooms:
        pts = np.array(room['polygon'], np.int32)
        cv2.polylines(overlay, [pts], True, (0, 0, 255), 2)
        x, y = room['polygon'][0]
        cv2.putText(overlay, str(room['id']), (x + 5, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    Image.fromarray(overlay).save(overlay_path)

    payload = {
        'source': stem,
        'room_count': len(rooms),
        'image_resolution': [img.size[1], img.size[0]],
        'rooms': rooms,
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)

    fieldnames = [
        'source', 'room_label', 'id', 'area_px', 'area_m2', 'approx_area_m2',
        'confidence', 'density', 'perimeter_px', 'center_x', 'center_y',
        'bbox_x1', 'bbox_y1', 'bbox_x2', 'bbox_y2', 'polygon', 'image_resolution'
    ]

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for room in rooms:
            bbox = room.get('bbox', [0, 0, 0, 0])
            writer.writerow(
                {
                    'source': stem,
                    'room_label': room.get('room_label', ''),
                    'id': room.get('id', ''),
                    'area_px': room.get('area_px', ''),
                    'area_m2': room.get('area_m2', ''),
                    'approx_area_m2': room.get('approx_area_m2', ''),
                    'confidence': room.get('confidence', ''),
                    'density': room.get('density', ''),
                    'perimeter_px': room.get('perimeter_px', ''),
                    'center_x': room.get('center_point', [0, 0])[0] if room.get('center_point') else '',
                    'center_y': room.get('center_point', [0, 0])[1] if room.get('center_point') else '',
                    'bbox_x1': bbox[0] if len(bbox) > 0 else '',
                    'bbox_y1': bbox[1] if len(bbox) > 1 else '',
                    'bbox_x2': bbox[2] if len(bbox) > 2 else '',
                    'bbox_y2': bbox[3] if len(bbox) > 3 else '',
                    'polygon': json.dumps(room.get('polygon', [])),
                    'image_resolution': f"{img.size[1]}x{img.size[0]}",
                }
            )

    return original_path, mask_path, overlay_path, json_path, csv_path


def process_single_image(input_path: Path, model, device, output_dir: Path, threshold: float, min_area_px: int, pixels_per_meter: float):
    img = Image.open(input_path).convert('RGB')
    mask, probs_np = predict_mask_with_probs(model, img, device, threshold=threshold)
    cleaned_mask = clean_mask(mask, min_area_px=min_area_px)
    rooms = extract_rooms_from_mask(cleaned_mask, min_area_px=min_area_px, probs=probs_np, pixels_per_meter=pixels_per_meter)

    stem = input_path.stem
    save_outputs(output_dir, img, cleaned_mask, rooms, stem)
    print(f'Processed image: {input_path}')
    print(f'  Rooms found: {len(rooms)}')
    print(f'  JSON saved: {output_dir / f"{stem}_rooms.json"}')


def process_pdf(pdf_path: Path, model, device, output_dir: Path, dpi: int, threshold: float, min_area_px: int, pixels_per_meter: float):
    pdf_bytes = pdf_path.read_bytes()
    pages = convert_pdf_to_images(pdf_bytes, dpi=dpi)
    if not pages:
        raise RuntimeError(f'No pages were extracted from PDF: {pdf_path}')

    print(f'Found {len(pages)} pages in {pdf_path}')

    page_results = []
    all_rooms = []

    for idx, pil_img in enumerate(pages, start=1):
        mask, probs_np = predict_mask_with_probs(model, pil_img, device, threshold=threshold)
        cleaned_mask = clean_mask(mask, min_area_px=min_area_px)
        rooms = extract_rooms_from_mask(cleaned_mask, min_area_px=min_area_px, probs=probs_np, pixels_per_meter=pixels_per_meter)

        stem = f'{pdf_path.stem}_page_{idx}'
        save_outputs(output_dir, pil_img, cleaned_mask, rooms, stem)

        page_result = {
            'page_index': idx,
            'source': stem,
            'room_count': len(rooms),
            'rooms': rooms,
        }
        page_results.append(page_result)
        all_rooms.extend(rooms)

        print(f'Processed page {idx}: {pdf_path}')
        print(f'  Rooms found: {len(rooms)}')
        print(f'  JSON saved: {output_dir / f"{stem}_rooms.json"}')

    summary_payload = {
        'source': pdf_path.stem,
        'page_count': len(pages),
        'total_rooms': len(all_rooms),
        'pages': page_results,
    }

    summary_path = output_dir / f'{pdf_path.stem}_summary.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary_payload, f, indent=2)

    summary_csv_path = output_dir / f'{pdf_path.stem}_summary.csv'
    with open(summary_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'pdf_name', 'page_index', 'source', 'room_label', 'id', 'area_px', 'area_m2',
            'approx_area_m2', 'confidence', 'density', 'perimeter_px', 'center_x', 'center_y',
            'bbox_x1', 'bbox_y1', 'bbox_x2', 'bbox_y2', 'polygon'
        ])
        for page in page_results:
            for room in page['rooms']:
                bbox = room.get('bbox', [0, 0, 0, 0])
                writer.writerow([
                    pdf_path.stem,
                    page['page_index'],
                    page['source'],
                    room.get('room_label', ''),
                    room.get('id', ''),
                    room.get('area_px', ''),
                    room.get('area_m2', ''),
                    room.get('approx_area_m2', ''),
                    room.get('confidence', ''),
                    room.get('density', ''),
                    room.get('perimeter_px', ''),
                    room.get('center_point', [0, 0])[0] if room.get('center_point') else '',
                    room.get('center_point', [0, 0])[1] if room.get('center_point') else '',
                    bbox[0] if len(bbox) > 0 else '',
                    bbox[1] if len(bbox) > 1 else '',
                    bbox[2] if len(bbox) > 2 else '',
                    bbox[3] if len(bbox) > 3 else '',
                    json.dumps(room.get('polygon', [])),
                ])

    print(f'  Combined PDF summary saved: {summary_path}')
    print(f'  Combined PDF CSV saved: {summary_csv_path}')
    return summary_payload


def write_directory_summary(output_dir: Path, summary_entries: list):
    directory_summary = {
        'total_pdfs': len(summary_entries),
        'pdfs': summary_entries,
    }

    summary_path = output_dir / 'all_pdfs_summary.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(directory_summary, f, indent=2)

    csv_path = output_dir / 'all_pdfs_summary.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'pdf_name', 'page_index', 'source', 'room_label', 'id', 'area_px', 'area_m2',
            'approx_area_m2', 'confidence', 'density', 'perimeter_px', 'center_x', 'center_y',
            'bbox_x1', 'bbox_y1', 'bbox_x2', 'bbox_y2', 'polygon'
        ])

        for entry in summary_entries:
            for page in entry.get('pages', []):
                for room in page.get('rooms', []):
                    bbox = room.get('bbox', [0, 0, 0, 0])
                    writer.writerow([
                        entry['source'],
                        page['page_index'],
                        page['source'],
                        room.get('room_label', ''),
                        room.get('id', ''),
                        room.get('area_px', ''),
                        room.get('area_m2', ''),
                        room.get('approx_area_m2', ''),
                        room.get('confidence', ''),
                        room.get('density', ''),
                        room.get('perimeter_px', ''),
                        room.get('center_point', [0, 0])[0] if room.get('center_point') else '',
                        room.get('center_point', [0, 0])[1] if room.get('center_point') else '',
                        bbox[0] if len(bbox) > 0 else '',
                        bbox[1] if len(bbox) > 1 else '',
                        bbox[2] if len(bbox) > 2 else '',
                        bbox[3] if len(bbox) > 3 else '',
                        json.dumps(room.get('polygon', [])),
                    ])

    print(f'  Directory summary JSON saved: {summary_path}')
    print(f'  Directory summary CSV saved: {csv_path}')


def main():
    parser = argparse.ArgumentParser(
        description='Run a trained floorplan U-Net model on PDFs or images, then export room polygons as JSON.'
    )
    parser.add_argument('--input', required=True, help='Input PDF or image file/folder')
    parser.add_argument('--model', default='model_best.pth', help='Path to the trained model checkpoint')
    parser.add_argument('--output-dir', default='inference_output', help='Directory to save outputs')
    parser.add_argument('--dpi', type=int, default=200, help='DPI used for PDF conversion (default: 200)')
    parser.add_argument('--threshold', type=float, default=0.5, help='Probability threshold for binary mask (default: 0.5)')
    parser.add_argument('--min-area-px', type=int, default=2000, help='Minimum contour area in pixels to keep as a room (default: 2000)')
    parser.add_argument('--pixels-per-meter', type=float, default=100.0, help='Scale used to estimate room area in square meters (default: 100.0)')
    parser.add_argument('--device', default='auto', choices=['auto', 'cpu', 'cuda'], help='Inference device')
    args = parser.parse_args()

    device_name = args.device
    if device_name == 'auto':
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    else:
        device = torch.device(args.device)

    model_path = resolve_model_path(args.model)
    if not os.path.exists(model_path):
        raise FileNotFoundError(f'Model file not found: {model_path}')

    model = load_model(model_path, device)
    print(f'Loaded model from: {model_path}')
    print(f'Inference device: {device}')

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_entries = []

    if input_path.is_dir():
        files = sorted(input_path.rglob('*'))
        pdfs = [f for f in files if f.is_file() and f.suffix.lower() == '.pdf']
        images = [f for f in files if f.is_file() and f.suffix.lower() in {'.png', '.jpg', '.jpeg'}]

        if not pdfs and not images:
            raise FileNotFoundError(f'No supported files found in directory: {input_path}')

        for pdf in pdfs:
            summary = process_pdf(
                pdf,
                model,
                device,
                output_dir / pdf.parent.name,
                args.dpi,
                args.threshold,
                args.min_area_px,
                args.pixels_per_meter,
            )
            summary_entries.append(summary)

        for image in images:
            process_single_image(
                image,
                model,
                device,
                output_dir / image.parent.name,
                args.threshold,
                args.min_area_px,
                args.pixels_per_meter,
            )

        write_directory_summary(output_dir, summary_entries)
    else:
        if input_path.suffix.lower() == '.pdf':
            summary = process_pdf(input_path, model, device, output_dir, args.dpi, args.threshold, args.min_area_px, args.pixels_per_meter)
            write_directory_summary(output_dir, [summary])
        else:
            process_single_image(input_path, model, device, output_dir, args.threshold, args.min_area_px, args.pixels_per_meter)

    print('Done.')


if __name__ == '__main__':
    main()
