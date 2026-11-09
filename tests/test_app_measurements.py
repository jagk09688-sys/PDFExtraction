import io

import cv2
import numpy as np
from PIL import Image

import app as floorplan_app


def test_save_corrections_reports_carpet_area_and_roll_length_separately(tmp_path, monkeypatch):
    monkeypatch.setattr(floorplan_app, "OUTPUT_DIR", str(tmp_path))
    client = floorplan_app.app.test_client()

    response = client.post(
        "/save_corrections",
        json={
            "pixels_per_meter": 100,
            "roll_width": 3.66,
            "results": [
                {
                    "id": 1,
                    "room_name": "Bedroom",
                    "include_in_carpet": True,
                    "polygon": [[0, 0], [400, 0], [400, 300], [0, 300]],
                },
                {
                    "id": 2,
                    "room_name": "Bathroom",
                    "include_in_carpet": False,
                    "polygon": [[500, 0], [800, 0], [800, 300], [500, 300]],
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["results"][0]["area_m2"] == 12.0
    assert payload["results"][0]["carpet_area_m2"] == 12.0
    assert payload["results"][0]["estimated_roll_length_m"] == 4.0
    assert payload["results"][1]["area_m2"] == 9.0
    assert payload["results"][1]["carpet_area_m2"] == 0.0
    assert payload["total_area_m2"] == 21.0
    assert payload["total_carpet_area_m2"] == 12.0
    assert payload["total_estimated_roll_length_m"] == 4.0


def test_extract_accepts_unscaled_upload_without_inventing_metres(tmp_path, monkeypatch):
    monkeypatch.setattr(floorplan_app, "OUTPUT_DIR", str(tmp_path))
    image = Image.new("RGB", (500, 400), "white")
    contour = np.array(
        [[[100, 100]], [[400, 100]], [[400, 300]], [[100, 300]]],
        dtype=np.int32,
    )
    room = {
        "polygon": [(100, 100), (400, 100), (400, 300), (100, 300)],
        "area_px": cv2.contourArea(contour),
        "contour": contour,
    }
    monkeypatch.setattr(floorplan_app, "convert_pdf_to_images", lambda *_args, **_kwargs: [image])
    monkeypatch.setattr(floorplan_app, "extract_pdf_text_items", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(floorplan_app, "extract_room_text", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(floorplan_app, "ocr_engine_available", lambda: True)
    monkeypatch.setattr(floorplan_app, "detect_rooms", lambda _image: (np.asarray(image), [room]))

    response = floorplan_app.app.test_client().post(
        "/extract",
        data={"pdf": (io.BytesIO(b"%PDF-test"), "plan.pdf"), "page_number": "1"},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"Calibrate" in response.data
    assert b"let pixelsPerMeter = null;" in response.data
    assert b"let pixelsPerMeter = None;" not in response.data
    assert b"Draw missing room" in response.data
    assert b"Calibrate Scale" in response.data
    assert b">12.0<" not in response.data
    assert b"Pixels per meter is required" not in response.data


def test_extract_calibrated_room_computes_dimensions_and_carpet_length(tmp_path, monkeypatch):
    monkeypatch.setattr(floorplan_app, "OUTPUT_DIR", str(tmp_path))
    image = Image.new("RGB", (500, 400), "white")
    contour = np.array(
        [[[100, 100]], [[400, 100]], [[400, 300]], [[100, 300]]],
        dtype=np.int32,
    )
    room = {
        "polygon": [(100, 100), (400, 100), (400, 300), (100, 300)],
        "area_px": cv2.contourArea(contour),
        "contour": contour,
    }
    monkeypatch.setattr(floorplan_app, "convert_pdf_to_images", lambda *_args, **_kwargs: [image])
    monkeypatch.setattr(floorplan_app, "extract_pdf_text_items", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(floorplan_app, "extract_room_text", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(floorplan_app, "ocr_engine_available", lambda: True)
    monkeypatch.setattr(floorplan_app, "detect_rooms", lambda _image: (np.asarray(image), [room]))

    response = floorplan_app.app.test_client().post(
        "/extract",
        data={
            "pdf": (io.BytesIO(b"%PDF-test"), "plan.pdf"),
            "page_number": "1",
            "pixels_per_meter": "100",
            "roll_width": "3.66",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b'class="area-m2">6.0<' in response.data
    assert b'class="length">3.0<' in response.data
    assert b'class="width">2.0<' in response.data
    assert b"Estimated Roll Length" in response.data
