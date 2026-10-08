import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import detect_rooms


def test_detect_rooms_handles_dark_floorplans():
    img = np.zeros((1200, 1200, 3), dtype=np.uint8)
    rooms = [(200, 200, 400, 400), (500, 200, 700, 350), (200, 600, 450, 900), (650, 600, 950, 900)]
    for x1, y1, x2, y2 in rooms:
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 0), 8)

    _, detected = detect_rooms(Image.fromarray(img), min_area_px=500)

    assert len(detected) >= 4


if __name__ == "__main__":
    test_detect_rooms_handles_dark_floorplans()
