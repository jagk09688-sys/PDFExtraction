"""Hybrid floorplan pipeline combining YOLOv8, U-Net, optional OCR, and room export.

This script keeps the current U-Net workflow as the main segmentation engine,
then optionally applies YOLOv8 detections and OCR for richer room metadata.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from infer_floorplan_segmentation import (
    load_model,
    predict_mask_with_probs,
    clean_mask,
    extract_rooms_from_mask,
    save_outputs,
    convert_pdf_to_images,
    resolve_model_path,
)
from yolo_detect import detect_room_boxes
from ocr_room_labels import extract_room_text

import numpy as np
import torch
from PIL import Image


def _normalize_bbox(bbox):
    """Convert bbox-like inputs into a [x1, y1, x2, y2] list when possible."""
    if bbox is None:
        return None

    if isinstance(bbox, dict):
        if {'x1', 'y1', 'x2', 'y2'} <= bbox.keys():
            return [float(bbox['x1']), float(bbox['y1']), float(bbox['x2']), float(bbox['y2'])]
        if {'left', 'top', 'right', 'bottom'} <= bbox.keys():
            return [float(bbox['left']), float(bbox['top']), float(bbox['right']), float(bbox['bottom'])]

    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        return [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]

    if isinstance(bbox, (list, tuple)) and len(bbox) >= 3 and all(isinstance(p, (list, tuple)) and len(p) >= 2 for p in bbox):
        xs = [float(p[0]) for p in bbox]
        ys = [float(p[1]) for p in bbox]
        return [min(xs), min(ys), max(xs), max(ys)]

    return None


def _bbox_overlap_score(room_bbox, candidate_bbox):
    if room_bbox is None or candidate_bbox is None:
        return 0.0

    x1 = max(room_bbox[0], candidate_bbox[0])
    y1 = max(room_bbox[1], candidate_bbox[1])
    x2 = min(room_bbox[2], candidate_bbox[2])
    y2 = min(room_bbox[3], candidate_bbox[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h

    room_area = max(1.0, (room_bbox[2] - room_bbox[0]) * (room_bbox[3] - room_bbox[1]))
    cand_area = max(1.0, (candidate_bbox[2] - candidate_bbox[0]) * (candidate_bbox[3] - candidate_bbox[1]))
    union = room_area + cand_area - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


def _attach_room_metadata(rooms, detections, text_items):
    for room in rooms:
        room['ocr_text'] = []
        room['yolo_detections'] = []

        room_bbox = _normalize_bbox(room.get('bbox'))

        if detections:
            matched_detections = []
            for detection in detections:
                detection_bbox = _normalize_bbox(detection.get('bbox'))
                if detection_bbox is None:
                    continue
                overlap = _bbox_overlap_score(room_bbox, detection_bbox)
                if overlap >= 0.05:
                    matched_detections.append(detection)

            room['yolo_detections'] = matched_detections

        if text_items:
            matched_text = []
            for item in text_items:
                item_bbox = _normalize_bbox(item.get('bbox'))
                if item_bbox is None:
                    matched_text.append(item)
                    continue

                overlap = _bbox_overlap_score(room_bbox, item_bbox)
                if overlap >= 0.01 or room_bbox is None:
                    matched_text.append(item)

            room['ocr_text'] = matched_text

    return rooms


def write_combined_summary(output_dir: Path, summary_entries: list[dict]):
    total_pages = sum(item.get('page_count', 0) for item in summary_entries)
    total_rooms = sum(item.get('total_rooms', 0) for item in summary_entries)

    combined = {
        'total_input_files': len(summary_entries),
        'total_pages': total_pages,
        'total_rooms': total_rooms,
        'files': summary_entries,
    }

    summary_path = output_dir / 'final_summary.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2)

    print(f'Combined summary saved: {summary_path}')


def run_pipeline(input_path: Path, model, device, output_dir: Path, args):
    if input_path.suffix.lower() == '.pdf':
        pages = convert_pdf_to_images(input_path.read_bytes(), dpi=args.dpi)
        page_results = []
        all_rooms = []

        for idx, pil_img in enumerate(pages, start=1):
            stem = f'{input_path.stem}_page_{idx}'
            mask, probs_np = predict_mask_with_probs(model, pil_img, device, threshold=args.threshold)
            cleaned_mask = clean_mask(mask, min_area_px=args.min_area_px)
            rooms = extract_rooms_from_mask(cleaned_mask, min_area_px=args.min_area_px, probs=probs_np, pixels_per_meter=args.pixels_per_meter)

            if args.yolo_model:
                detections = detect_room_boxes(pil_img, args.yolo_model, conf=args.yolo_conf, iou=args.yolo_iou)
            else:
                detections = []

            if args.ocr:
                ocr_path = output_dir / f'{stem}_ocr.png'
                pil_img.save(ocr_path)
                text_items = extract_room_text(ocr_path, prefer=args.ocr_engine)
            else:
                text_items = []

            rooms = _attach_room_metadata(rooms, detections, text_items)

            save_outputs(output_dir, pil_img, cleaned_mask, rooms, stem)

            page_result = {
                'page_index': idx,
                'source': stem,
                'room_count': len(rooms),
                'rooms': rooms,
            }
            page_results.append(page_result)
            all_rooms.extend(rooms)

            print(f'Processed {stem}: rooms={len(rooms)}')

        return {
            'source': input_path.stem,
            'input_file': str(input_path),
            'page_count': len(page_results),
            'total_rooms': len(all_rooms),
            'pages': page_results,
        }

    pil_img = Image.open(input_path).convert('RGB')
    stem = input_path.stem
    mask, probs_np = predict_mask_with_probs(model, pil_img, device, threshold=args.threshold)
    cleaned_mask = clean_mask(mask, min_area_px=args.min_area_px)
    rooms = extract_rooms_from_mask(cleaned_mask, min_area_px=args.min_area_px, probs=probs_np, pixels_per_meter=args.pixels_per_meter)

    detections = detect_room_boxes(pil_img, args.yolo_model, conf=args.yolo_conf, iou=args.yolo_iou) if args.yolo_model else []
    text_items = extract_room_text(input_path, prefer=args.ocr_engine) if args.ocr else []

    rooms = _attach_room_metadata(rooms, detections, text_items)

    save_outputs(output_dir, pil_img, cleaned_mask, rooms, stem)

    page_result = {
        'page_index': 1,
        'source': stem,
        'room_count': len(rooms),
        'rooms': rooms,
    }

    print(f'Processed {stem}: rooms={len(rooms)}')

    return {
        'source': stem,
        'input_file': str(input_path),
        'page_count': 1,
        'total_rooms': len(rooms),
        'pages': [page_result],
    }


def main():
    parser = argparse.ArgumentParser(description='Hybrid floorplan pipeline with YOLOv8, U-Net, and optional OCR.')
    parser.add_argument('--input', required=True, help='Input PDF or image file/folder')
    parser.add_argument('--model', default='model_best.pth', help='Path to trained U-Net checkpoint')
    parser.add_argument('--output-dir', default='hybrid_output', help='Output directory')
    parser.add_argument('--dpi', type=int, default=200, help='DPI for PDF conversion')
    parser.add_argument('--threshold', type=float, default=0.5, help='Segmentation threshold')
    parser.add_argument('--min-area-px', type=int, default=2000, help='Minimum contour area')
    parser.add_argument('--pixels-per-meter', type=float, default=100.0, help='Pixels-per-meter scale')
    parser.add_argument('--device', default='auto', choices=['auto', 'cpu', 'cuda'])
    parser.add_argument('--yolo-model', default='', help='Optional path to YOLOv8 weights (.pt)')
    parser.add_argument('--yolo-conf', type=float, default=0.25, help='YOLO confidence threshold')
    parser.add_argument('--yolo-iou', type=float, default=0.5, help='YOLO IoU threshold')
    parser.add_argument('--ocr', action='store_true', help='Enable OCR text extraction')
    parser.add_argument('--ocr-engine', default='surya', choices=['surya', 'paddleocr'], help='OCR engine preference')
    args = parser.parse_args()

    device_name = args.device
    if device_name == 'auto':
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    else:
        device = torch.device(args.device)

    model_path = resolve_model_path(args.model)
    model = load_model(model_path, device)
    print(f'Loaded U-Net from: {model_path}')

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_entries = []

    if input_path.is_dir():
        files = sorted(input_path.rglob('*'))
        pdfs = [p for p in files if p.is_file() and p.suffix.lower() == '.pdf']
        images = [p for p in files if p.is_file() and p.suffix.lower() in {'.png', '.jpg', '.jpeg'}]

        for pdf in pdfs:
            summary = run_pipeline(pdf, model, device, output_dir / pdf.parent.name, args)
            summary_entries.append(summary)

        for image in images:
            summary = run_pipeline(image, model, device, output_dir / image.parent.name, args)
            summary_entries.append(summary)

        write_combined_summary(output_dir, summary_entries)
    else:
        summary = run_pipeline(input_path, model, device, output_dir, args)
        write_combined_summary(output_dir, [summary])

    print('Hybrid pipeline complete.')


if __name__ == '__main__':
    main()
