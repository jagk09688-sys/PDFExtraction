import io
import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

import ai_room_analysis
import app as floorplan_app


def _room(name, room_type, recommended, confidence=0.95):
    return {
        "room_name": name,
        "room_type": room_type,
        "polygon": [[100, 100], [500, 100], [500, 500], [100, 500]],
        "carpet_recommended": recommended,
        "confidence": confidence,
        "reason": "Clear room boundary and label",
    }


def test_ai_room_parser_excludes_wet_rooms_and_includes_kitchens():
    response = json.dumps(
        {
            "rooms": [
                _room("Bathroom", "bathroom", True),
                _room("Kitchen", "kitchen", False),
                _room("Bedroom", "bedroom", True, confidence=0.4),
                _room("Living", "living room", True),
                _room("Unclassified", "unknown", True),
            ]
        }
    )

    rooms = ai_room_analysis.parse_room_analysis(response, (101, 101))

    assert [room["include_in_carpet"] for room in rooms] == [
        False,
        True,
        False,
        True,
        False,
    ]
    assert rooms[2]["ai_review_required"] is True
    assert rooms[4]["ai_review_required"] is True
    assert rooms[0]["polygon"] == [(10, 10), (50, 10), (50, 50), (10, 50)]


def test_ai_room_parser_rejects_invalid_polygons():
    response = json.dumps(
        {
            "rooms": [
                {
                    **_room("Bedroom", "bedroom", True),
                    "polygon": [[100, 100], [500, 500], [100, 500], [500, 100]],
                }
            ]
        }
    )

    with pytest.raises(ai_room_analysis.AIAnalysisError, match="unusable boundary"):
        ai_room_analysis.parse_room_analysis(response, (1000, 1000))


def test_openai_request_uses_only_an_explicitly_invoked_page_image(monkeypatch):
    calls = {}

    class FakeAPIError(Exception):
        pass

    class FakeOpenAI:
        def __init__(self, **kwargs):
            calls["client"] = kwargs
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self._create)
            )

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def _create(self, **kwargs):
            calls["request"] = kwargs
            content = json.dumps({"rooms": [_room("Kitchen", "kitchen", False)]})
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content=content))
                ]
            )

    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(APIError=FakeAPIError, OpenAI=FakeOpenAI),
    )
    page = Image.new("RGB", (200, 300), "white")

    rooms = ai_room_analysis.analyze_floorplan_page(
        page, api_key="test-key", model="test-model"
    )

    assert calls["client"]["api_key"] == "test-key"
    assert calls["request"]["model"] == "test-model"
    image_message = calls["request"]["messages"][0]["content"][1]["image_url"]
    assert image_message["url"].startswith("data:image/jpeg;base64,")
    assert rooms[0]["include_in_carpet"] is True


def test_extract_returns_ai_rooms_and_excludes_wet_rooms_from_totals(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(floorplan_app, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(floorplan_app.Config, "OPENAI_API_KEY", "test-key")
    image = Image.new("RGB", (500, 400), "white")
    polygon = [[100, 100], [300, 100], [300, 300], [100, 300]]
    ai_rooms = [
        {
            "room_name": "Kitchen",
            "ai_room_type": "kitchen",
            "ai_reason": "Dry room.",
            "ai_confidence": 0.9,
            "ai_review_required": False,
            "include_in_carpet": True,
            "polygon": polygon,
        },
        {
            "room_name": "Bathroom",
            "ai_room_type": "bathroom",
            "ai_reason": "Wet area.",
            "ai_confidence": 0.95,
            "ai_review_required": False,
            "include_in_carpet": False,
            "polygon": [[350, 100], [450, 100], [450, 200], [350, 200]],
        },
    ]
    monkeypatch.setattr(
        floorplan_app,
        "analyze_floorplan_page",
        lambda *_args, **_kwargs: ai_rooms,
    )
    monkeypatch.setattr(
        floorplan_app,
        "convert_pdf_to_images",
        lambda *_args, **_kwargs: [image],
    )
    monkeypatch.setattr(
        floorplan_app, "extract_pdf_text_items", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(floorplan_app, "extract_room_text", lambda *_args: [])
    monkeypatch.setattr(floorplan_app, "ocr_engine_available", lambda: True)
    monkeypatch.setattr(floorplan_app, "find_floorplan_region", lambda *_args: None)
    monkeypatch.setattr(
        floorplan_app,
        "detect_rooms",
        lambda *_args: pytest.fail("AI results should replace contour detection"),
    )

    captured = {}

    original_template = floorplan_app.render_template

    def capture_template(template, **context):
        captured.update(context)
        return original_template(template, **context)

    monkeypatch.setattr(floorplan_app, "render_template", capture_template)
    response = floorplan_app.app.test_client().post(
        "/extract",
        data={
            "pdf": (io.BytesIO(b"%PDF-test"), "plan.pdf"),
            "page_number": "1",
            "pixels_per_meter": "100",
            "use_ai": "1",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert captured["ai_assisted"] is True
    assert [room["room_name"] for room in captured["results"]] == [
        "Kitchen",
        "Bathroom",
    ]
    assert [room["include_in_carpet"] for room in captured["results"]] == [
        True,
        False,
    ]
    assert captured["total_room_area_m2"] == 5.0
    assert captured["total_carpet_area_m2"] == 4.0
    assert captured["total_carpet_required_m"] == 2.0
    kitchen_row = html.split('<tr data-id="1">', 1)[1].split("</tr>", 1)[0]
    bathroom_row = html.split('<tr data-id="2">', 1)[1].split("</tr>", 1)[0]
    assert 'value="Kitchen"' in kitchen_row
    assert "checked" in kitchen_row
    assert "checked" not in bathroom_row


def test_ai_extraction_without_api_key_fails_before_processing(monkeypatch):
    monkeypatch.setattr(floorplan_app.Config, "OPENAI_API_KEY", "")
    monkeypatch.setattr(
        floorplan_app,
        "convert_pdf_to_images",
        lambda *_args, **_kwargs: pytest.fail("PDF should not be processed"),
    )

    response = floorplan_app.app.test_client().post(
        "/extract",
        data={
            "pdf": (io.BytesIO(b"%PDF-test"), "plan.pdf"),
            "use_ai": "1",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 503
    assert response.get_json()["error"] == (
        "AI analysis is unavailable. Set OPENAI_API_KEY in your environment or .env file."
    )


def test_upload_without_ai_checkbox_does_not_call_openai(monkeypatch, tmp_path):
    monkeypatch.setattr(floorplan_app, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(floorplan_app.Config, "OPENAI_API_KEY", "test-key")
    image = Image.new("RGB", (500, 400), "white")
    contour = np.array(
        [[[100, 100]], [[300, 100]], [[300, 300]], [[100, 300]]],
        dtype=np.int32,
    )
    room = {
        "polygon": [(100, 100), (300, 100), (300, 300), (100, 300)],
        "area_px": 40000,
        "contour": contour,
    }
    monkeypatch.setattr(
        floorplan_app,
        "analyze_floorplan_page",
        lambda *_args, **_kwargs: pytest.fail("OpenAI must remain opt-in"),
    )
    monkeypatch.setattr(
        floorplan_app,
        "convert_pdf_to_images",
        lambda *_args, **_kwargs: [image],
    )
    monkeypatch.setattr(
        floorplan_app, "extract_pdf_text_items", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(floorplan_app, "extract_room_text", lambda *_args: [])
    monkeypatch.setattr(floorplan_app, "ocr_engine_available", lambda: True)
    monkeypatch.setattr(floorplan_app, "find_floorplan_region", lambda *_args: None)
    monkeypatch.setattr(
        floorplan_app, "detect_rooms", lambda *_args: (np.asarray(image), [room])
    )

    response = floorplan_app.app.test_client().post(
        "/extract",
        data={
            "pdf": (io.BytesIO(b"%PDF-test"), "plan.pdf"),
            "page_number": "1",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"OpenAI analyzed this page" not in response.data
