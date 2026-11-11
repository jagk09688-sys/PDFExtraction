"""Optional OpenAI vision analysis for room outlines and carpet recommendations."""

from __future__ import annotations

import base64
import io
import json
import math
import re
from typing import Any

from PIL import Image
from shapely.geometry import Polygon


class AIAnalysisError(Exception):
    """An explicit, user-displayable failure from AI room analysis."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


_WET_ROOM_RE = re.compile(
    r"\b(?:bath(?:room)?s?|ensuite|en\s*suite|wc|toilet|powder(?:\s+room)?|"
    r"laundry|utility|shower|wet\s+area)\b",
    re.IGNORECASE,
)
_KITCHEN_RE = re.compile(r"\bkitchen\b", re.IGNORECASE)


def _is_finite_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def parse_room_analysis(content: str, image_size: tuple[int, int]) -> list[dict[str, Any]]:
    """Validate normalized model output and map polygons to rendered-image pixels."""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise AIAnalysisError("OpenAI returned invalid JSON for the room analysis.") from error

    if not isinstance(payload, dict) or not isinstance(payload.get("rooms"), list):
        raise AIAnalysisError("OpenAI returned an invalid room-analysis result.")
    if len(payload["rooms"]) > 60:
        raise AIAnalysisError("OpenAI returned too many room candidates to review safely.")

    image_width, image_height = image_size
    if image_width < 1 or image_height < 1:
        raise AIAnalysisError("The rendered floorplan has invalid dimensions.")

    rooms = []
    for index, item in enumerate(payload["rooms"], start=1):
        if not isinstance(item, dict):
            raise AIAnalysisError(f"OpenAI returned an invalid record for room {index}.")

        name = item.get("room_name")
        room_type = item.get("room_type")
        reason = item.get("reason", "")
        confidence = item.get("confidence")
        recommended = item.get("carpet_recommended")
        normalized_polygon = item.get("polygon")
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name) > 100
            or not isinstance(room_type, str)
            or not room_type.strip()
            or len(room_type) > 80
            or not isinstance(reason, str)
            or not _is_finite_number(confidence)
            or not 0 <= confidence <= 1
            or not isinstance(recommended, bool)
            or not isinstance(normalized_polygon, list)
            or not 3 <= len(normalized_polygon) <= 80
        ):
            raise AIAnalysisError(f"OpenAI returned invalid details for room {index}.")

        normalized_points = []
        for point in normalized_polygon:
            if (
                not isinstance(point, list)
                or len(point) != 2
                or any(
                    not _is_finite_number(value)
                    or not 0 <= value <= 1000
                    for value in point
                )
            ):
                raise AIAnalysisError(f"OpenAI returned invalid boundary points for room {index}.")
            normalized_points.append((float(point[0]), float(point[1])))

        normalized_shape = Polygon(normalized_points)
        if not normalized_shape.is_valid or normalized_shape.area < 10:
            raise AIAnalysisError(f"OpenAI returned an unusable boundary for room {index}.")

        points = [
            (
                round(x / 1000 * (image_width - 1)),
                round(y / 1000 * (image_height - 1)),
            )
            for x, y in normalized_points
        ]
        pixel_shape = Polygon(points)
        if not pixel_shape.is_valid or pixel_shape.area <= 0:
            raise AIAnalysisError(f"OpenAI returned an unusable boundary for room {index}.")

        classification = f"{name} {room_type}"
        is_wet_room = _WET_ROOM_RE.search(classification) is not None
        is_kitchen = _KITCHEN_RE.search(classification) is not None
        is_uncertain_type = room_type.strip().casefold() in {
            "unknown",
            "other",
            "uncertain",
            "unlabeled",
            "unidentified",
        }
        if is_wet_room:
            include_in_carpet = False
        elif is_kitchen:
            include_in_carpet = True
        elif confidence < 0.65 or is_uncertain_type:
            include_in_carpet = False
        else:
            include_in_carpet = recommended

        rooms.append(
            {
                "room_name": name.strip(),
                "ai_room_type": room_type.strip(),
                "ai_reason": " ".join(reason[:1000].split())[:300],
                "ai_confidence": float(confidence),
                "ai_review_required": confidence < 0.65 or is_uncertain_type,
                "include_in_carpet": include_in_carpet,
                "polygon": points,
            }
        )

    if not rooms:
        raise AIAnalysisError(
            "AI could not identify any clear room boundaries on this page. "
            "Try a clearer plan or draw the room boundaries manually.",
            status_code=422,
        )
    return rooms


def analyze_floorplan_page(
    image: Image.Image, api_key: str, model: str = "gpt-4o-mini"
) -> list[dict[str, Any]]:
    """Send only the selected rendered page to OpenAI and parse its room draft."""
    if not api_key.strip():
        raise AIAnalysisError(
            "AI analysis is unavailable: set OPENAI_API_KEY in your environment or .env file.",
            status_code=503,
        )

    try:
        from openai import APIError, OpenAI
    except ImportError as error:
        raise AIAnalysisError(
            "AI analysis requires the OpenAI package. Install it with "
            "`pip install -r requirements.txt` and restart the app.",
            status_code=503,
        ) from error

    analysis_image = image.convert("RGB")
    analysis_image.thumbnail((2048, 2048), Image.LANCZOS)
    image_buffer = io.BytesIO()
    analysis_image.save(image_buffer, format="JPEG", quality=88, optimize=True)
    image_data = base64.b64encode(image_buffer.getvalue()).decode("ascii")
    prompt = (
        "Analyze this scanned or marked-up architectural floor plan. It may be rotated; "
        "interpret its orientation, but express all coordinates in the image as shown. "
        "Return a JSON object with a 'rooms' array. For each distinct enclosed interior "
        "room, return room_name, room_type, polygon, carpet_recommended, confidence, "
        "and reason. Do not include garages, outdoor areas, title blocks, annotations, "
        "or dimension strings as rooms. Trace each polygon around the inside edge of "
        "the visible room boundary. Polygon coordinates must be [x,y] pairs normalized "
        "from 0 to 1000 relative to the full image width and height. Do not invent "
        "boundaries: omit a room if its boundary cannot be identified clearly. "
        "Recommend carpet for dry living spaces, bedrooms, halls, and kitchens. "
        "Do not recommend carpet for bathrooms, ensuites, toilets, powder rooms, "
        "showers, laundries, or other wet areas. If uncertain, set confidence low, "
        "carpet_recommended false, and explain the uncertainty. Confidence must be "
        "between 0 and 1. Return JSON only."
    )

    try:
        with OpenAI(api_key=api_key, timeout=120, max_retries=1) as client:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
    except APIError as error:
        raise AIAnalysisError(
            "OpenAI room analysis failed. Check your API key, model access, quota, "
            "and network connection."
        ) from error

    if not response.choices or not response.choices[0].message.content:
        raise AIAnalysisError("OpenAI returned an empty room-analysis result.")
    return parse_room_analysis(response.choices[0].message.content, image.size)
