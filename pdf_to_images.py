"""Convert PDFs to image files for annotation/training.

Usage:
  python pdf_to_images.py --input-dir path/to/pdfs --output-dir dataset/images --dpi 300
"""
import os
import argparse
from pdf2image import convert_from_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input-dir', required=True)
    p.add_argument('--output-dir', required=True)
    p.add_argument('--dpi', type=int, default=300)
    p.add_argument('--pages', default=None, help='comma-separated page numbers (1-based) or "all"')
    args = p.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    for fn in os.listdir(args.input_dir):
        if not fn.lower().endswith('.pdf'):
            continue
        path = os.path.join(args.input_dir, fn)
        basename = os.path.splitext(fn)[0]
        try:
            if args.pages and args.pages.lower() != 'all':
                pages = [int(x) for x in args.pages.split(',')]
                images = convert_from_path(path, dpi=args.dpi, first_page=min(pages), last_page=max(pages))
                # filter pages
                sel = []
                for i, img in enumerate(images, start=min(pages)):
                    if i in pages:
                        sel.append((i, img))
                images = [img for (_, img) in sel]
            else:
                images = convert_from_path(path, dpi=args.dpi)
        except Exception as e:
            print('Failed to convert', path, e)
            continue
        for i, img in enumerate(images, start=1):
            out_name = f"{basename}_page{i}.png"
            out_path = os.path.join(args.output_dir, out_name)
            img.save(out_path)
            print('Saved', out_path)


if __name__ == '__main__':
    main()
