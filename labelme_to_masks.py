"""Convert LabelMe JSON annotations to binary mask PNGs.

LabelMe shape format is expected. Each json corresponds to an image file (same base name).
By default this script treats any polygon as 'room' (filled) unless a list of labels is provided.

Usage:
  python labelme_to_masks.py --images dataset/images --annotations labelme_json --output dataset/masks
"""
import os
import argparse
import json
import cv2
import numpy as np


def json_to_mask(json_path, labels=None):
    with open(json_path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    img_h = data.get('imageHeight')
    img_w = data.get('imageWidth')
    mask = np.zeros((img_h, img_w), dtype=np.uint8)
    for shape in data.get('shapes', []):
        label = shape.get('label')
        if labels and label not in labels:
            continue
        points = shape.get('points', [])
        if not points:
            continue
        poly = np.array(points, dtype=np.int32)
        cv2.fillPoly(mask, [poly], 255)
    return mask


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--images', required=True)
    p.add_argument('--annotations', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--labels', default='', help='comma-separated label names to include (default: all)')
    args = p.parse_args()

    labels = [x.strip() for x in args.labels.split(',')] if args.labels else None
    os.makedirs(args.output, exist_ok=True)

    for fn in os.listdir(args.annotations):
        if not fn.lower().endswith('.json'):
            continue
        jpath = os.path.join(args.annotations, fn)
        base = os.path.splitext(fn)[0]
        # find image file with same base
        possible = [base + ext for ext in ('.png', '.jpg', '.jpeg')]
        img_file = None
        for pfn in possible:
            if os.path.exists(os.path.join(args.images, pfn)):
                img_file = pfn; break
        if img_file is None:
            print('Image not found for', fn)
            continue
        mask = json_to_mask(jpath, labels=labels)
        out_path = os.path.join(args.output, base + '.png')
        cv2.imwrite(out_path, mask)
        print('Wrote mask', out_path)


if __name__ == '__main__':
    main()
