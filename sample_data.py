"""Generate a tiny synthetic floorplan image and matching mask for testing.

Creates:
  dataset/train/images/sample1.png
  dataset/train/masks/sample1.png
  dataset/val/images/sample1.png
  dataset/val/masks/sample1.png

Run:
  python sample_data.py
"""
from PIL import Image, ImageDraw
import os


def make_dirs():
    for split in ('train', 'val'):
        for sub in ('images', 'masks'):
            d = os.path.join('dataset', split, sub)
            os.makedirs(d, exist_ok=True)


def create_sample(out_img_path, out_mask_path):
    W, H = 800, 600
    img = Image.new('RGB', (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    # draw simple rooms as rectangles with walls
    rooms = [ (50, 50, 350, 300), (400, 80, 750, 500) ]
    for r in rooms:
        draw.rectangle(r, outline=(0,0,0), width=4)
        # add a door line
        x1, y1, x2, y2 = r
        draw.line([(x2, y1+40),(x2+10, y1+40)], fill=(0,0,0), width=4)

    img.save(out_img_path)

    # mask: fill rooms
    mask = Image.new('L', (W, H), 0)
    md = ImageDraw.Draw(mask)
    for r in rooms:
        md.rectangle(r, fill=255)
    mask.save(out_mask_path)


def main():
    make_dirs()
    paths = [
        ('dataset/train/images/sample1.png','dataset/train/masks/sample1.png'),
        ('dataset/val/images/sample1.png','dataset/val/masks/sample1.png'),
    ]
    for img_p, mask_p in paths:
        create_sample(img_p, mask_p)
        print('Wrote', img_p, mask_p)


if __name__ == '__main__':
    main()
