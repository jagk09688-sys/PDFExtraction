"""Optional YOLOv8 room detection helpers.

This module wraps Ultralytics YOLOv8 for optional floorplan detection.
If the ultralytics package is unavailable, the functions simply return empty results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def detect_room_boxes(image, model_path: str | None = None, conf: float = 0.25, iou: float = 0.5):
    """Run YOLOv8 on a PIL image if a model path is provided.

    Returns a list of dictionaries with box coordinates and labels.
    """
    if not model_path:
        return []

    try:
        from ultralytics import YOLO
    except Exception as exc:
        print(f"YOLOv8 is not available: {exc}")
        return []

    model = YOLO(model_path)

    results = model(image, verbose=False, conf=conf, iou=iou)
    detections = []

    for result in results:
        boxes = getattr(result, 'boxes', None)
        if boxes is None:
            continue

        for box in boxes:
            xyxy = box.xyxy[0].cpu().tolist()
            cls_index = int(box.cls[0].item()) if hasattr(box, 'cls') else 0
            cls_name = result.names.get(cls_index, str(cls_index)) if hasattr(result, 'names') else str(cls_index)
            detections.append(
                {
                    'class_name': cls_name,
                    'bbox': [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])],
                    'confidence': float(box.conf[0].item()) if hasattr(box, 'conf') else 0.0,
                }
            )

    return detections
