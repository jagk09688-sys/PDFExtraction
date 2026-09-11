"""Prepare a train/val floorplan dataset from PDFs.

This script does three things:
1. Splits PDFs from an input folder into train/val partitions.
2. Converts each PDF page into PNG images.
3. If LabelMe JSON annotations are available, converts them into matching masks.

If annotations are not present, the script can optionally create blank masks so the
expected train/val/image/mask structure exists immediately.

Example:
    python prepare_floorplan_dataset.py --input-dir Dataset --output-dir dataset_ready --val-ratio 0.2 --dpi 300 --blank-masks
"""

import argparse
import io
import json
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

try:
    import pymupdf
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None

try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None


def split_pdfs(pdfs, val_ratio=0.2, seed=42):
    pdfs = sorted(pdfs)
    if len(pdfs) < 2:
        return pdfs, []

    rng = random.Random(seed)
    shuffled = pdfs[:]
    rng.shuffle(shuffled)

    val_count = max(1, round(len(shuffled) * val_ratio))
    if val_count >= len(shuffled):
        val_count = len(shuffled) - 1

    val_pdfs = shuffled[:val_count]
    train_pdfs = shuffled[val_count:]
    return train_pdfs, val_pdfs


def convert_pdf_to_images(pdf_path: Path, output_dir: Path, dpi: int = 300):
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = []

    poppler_bin = Path(__file__).resolve().parent / 'poppler-windows' / 'Library' / 'bin'

    if pymupdf is not None:
        try:
            doc = pymupdf.open(pdf_path)
            zoom = dpi / 72.0
            for page_index in range(len(doc)):
                page = doc[page_index]
                mat = pymupdf.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_data = pix.tobytes('ppm')
                image = Image.open(io.BytesIO(img_data)).convert('RGB')

                out_name = f'{pdf_path.stem}_page{page_index + 1}.png'
                out_path = output_dir / out_name
                image.save(out_path)
                saved_paths.append(out_path)
            doc.close()
            return saved_paths
        except Exception as exc:
            print(f'PyMuPDF conversion failed for {pdf_path}: {exc}. Falling back to pdf2image.')

    if convert_from_path is None:
        raise RuntimeError('Neither PyMuPDF nor pdf2image is available for PDF conversion.')

    poppler_path = str(poppler_bin) if poppler_bin.exists() else None

    try:
        images = convert_from_path(str(pdf_path), dpi=dpi, poppler_path=poppler_path)
    except Exception as exc:
        raise RuntimeError(f'Failed to convert PDF: {pdf_path} ({exc})') from exc

    for page_index, image in enumerate(images, start=1):
        out_name = f'{pdf_path.stem}_page{page_index}.png'
        out_path = output_dir / out_name
        image.save(out_path)
        saved_paths.append(out_path)

    return saved_paths


def json_to_mask(json_path: Path):
    with open(json_path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)

    img_h = int(data.get('imageHeight', 0))
    img_w = int(data.get('imageWidth', 0))

    if img_h == 0 or img_w == 0:
        raise ValueError(f'Annotation {json_path} is missing image dimensions.')

    mask = np.zeros((img_h, img_w), dtype=np.uint8)

    for shape in data.get('shapes', []):
        points = shape.get('points', [])
        if not points:
            continue
        poly = np.array(points, dtype=np.int32)
        cv2.fillPoly(mask, [poly], 255)

    return mask


def generate_masks_from_annotations(images_dir: Path, annotations_dir: Path, masks_dir: Path):
    if not annotations_dir.exists():
        return 0

    masks_dir.mkdir(parents=True, exist_ok=True)
    generated = 0

    for image_path in sorted(images_dir.glob('*.png')):
        json_path = annotations_dir / f'{image_path.stem}.json'

        if json_path.exists():
            mask = json_to_mask(json_path)
            cv2.imwrite(str(masks_dir / f'{image_path.stem}.png'), mask)
            generated += 1

    return generated


def create_blank_masks(images_dir: Path, masks_dir: Path):
    masks_dir.mkdir(parents=True, exist_ok=True)

    for image_path in sorted(images_dir.glob('*.png')):
        img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        blank = np.zeros_like(img, dtype=np.uint8)
        cv2.imwrite(str(masks_dir / f'{image_path.stem}.png'), blank)


def build_dataset(input_dir: Path, output_dir: Path, val_ratio: float, dpi: int, annotations_dir: Path | None, blank_masks: bool, seed: int):
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()

    pdf_files = sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == '.pdf'])
    if not pdf_files:
        raise FileNotFoundError(f'No PDF files found in: {input_dir}')

    train_pdfs, val_pdfs = split_pdfs(pdf_files, val_ratio=val_ratio, seed=seed)

    print(f'Found {len(pdf_files)} PDFs.')
    print(f'Train PDFs: {len(train_pdfs)}')
    print(f'Validation PDFs: {len(val_pdfs)}')

    for split_name, pdf_list in [('train', train_pdfs), ('val', val_pdfs)]:
        split_images_dir = output_dir / split_name / 'images'
        split_masks_dir = output_dir / split_name / 'masks'
        split_images_dir.mkdir(parents=True, exist_ok=True)

        for pdf_path in pdf_list:
            converted = convert_pdf_to_images(pdf_path, split_images_dir, dpi=dpi)
            print(f'Converted {pdf_path.name} -> {len(converted)} page images')

        if annotations_dir is not None:
            generated = generate_masks_from_annotations(split_images_dir, annotations_dir, split_masks_dir)
            print(f'Generated masks for {generated} images in {split_name}')
        elif blank_masks:
            create_blank_masks(split_images_dir, split_masks_dir)
            print(f'Created blank masks for {split_name}')

    if annotations_dir is None and not blank_masks:
        print('\nNo annotations directory was provided, so masks were not created.')
        print('Add --annotations <folder> later, or rerun with --blank-masks to create placeholder masks.')

    print(f'\nDataset ready at: {output_dir}')
    print('Expected structure:')
    print(f'  {output_dir}/train/images')
    print(f'  {output_dir}/train/masks')
    print(f'  {output_dir}/val/images')
    print(f'  {output_dir}/val/masks')


def main():
    parser = argparse.ArgumentParser(
        description='Prepare a train/val floorplan dataset from PDFs and optional LabelMe annotations.'
    )
    parser.add_argument('--input-dir', required=True, help='Folder containing PDF files')
    parser.add_argument('--output-dir', default='prepared_dataset', help='Where to write the train/val dataset')
    parser.add_argument('--annotations', default=None, help='Optional folder containing LabelMe JSON annotations')
    parser.add_argument('--val-ratio', type=float, default=0.2, help='Validation split ratio (default: 0.2)')
    parser.add_argument('--dpi', type=int, default=300, help='PDF conversion DPI (default: 300)')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for consistent train/val splitting')
    parser.add_argument('--blank-masks', action='store_true', help='Create blank masks if annotations are unavailable')
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    annotations_dir = Path(args.annotations) if args.annotations else None

    if not input_dir.exists():
        raise FileNotFoundError(f'Input directory not found: {input_dir}')

    if args.val_ratio <= 0 or args.val_ratio >= 1:
        raise ValueError('val-ratio must be between 0 and 1 (exclusive).')

    build_dataset(
        input_dir=input_dir,
        output_dir=output_dir,
        val_ratio=args.val_ratio,
        dpi=args.dpi,
        annotations_dir=annotations_dir,
        blank_masks=args.blank_masks,
        seed=args.seed,
    )


if __name__ == '__main__':
    main()
