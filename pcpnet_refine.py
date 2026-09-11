"""Optional PCP-Net refinement helpers.

This module is a lightweight wrapper for a PCP-Net style boundary refinement step.
The current implementation is intentionally conservative: if the referenced model or
package is not installed, it simply returns the original room polygons and mask.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np


def refine_room_polygons(mask: np.ndarray, rooms: list[dict[str, Any]], model_path: str | None = None):
    """Optional refinement step for predicted room polygons.

    If a PCP-Net model is not available, this returns the original mask and rooms
    unchanged so the rest of the pipeline continues working.
    """
    if not model_path:
        return mask, rooms

    try:
        # Place your PCP-Net loader here if you add a model implementation later.
        # Example: from pcpnet import PCPNetModel
        # model = PCPNetModel(model_path)
        # refined_mask, refined_rooms = model.refine(mask, rooms)
        # return refined_mask, refined_rooms
        raise ImportError('PCP-Net model integration not configured yet')
    except Exception as exc:
        print(f"PCP-Net refinement unavailable: {exc}")
        return mask, rooms


def refine_binary_mask(mask: np.ndarray, model_path: str | None = None):
    """Convenience wrapper for mask refinement."""
    if mask is None:
        return mask

    if not model_path:
        return mask

    refined_mask, _ = refine_room_polygons(mask, [], model_path=model_path)
    return refined_mask
