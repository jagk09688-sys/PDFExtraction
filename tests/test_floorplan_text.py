import numpy as np
from PIL import Image

from floorplan_text import (
    attach_ocr_to_rooms,
    extract_pdf_text_items,
    merge_text_items,
    parse_dimension_pair,
    parse_single_measurement,
)
from ocr_room_labels import extract_text_with_rapidocr


def test_parse_metric_dimension_pair_and_convert_explicit_unit():
    result = parse_dimension_pair("BEDROOM 3.60 x 4.20 m")

    assert result is not None
    assert result["length_m"] == 4.2
    assert result["width_m"] == 3.6
    assert result["unit"] == "m"


def test_parse_millimetres_and_do_not_guess_missing_units():
    metric = parse_dimension_pair("3600 x 4200 mm")
    unlabelled = parse_dimension_pair("3.6 x 4.2")

    assert metric["length_m"] == 4.2
    assert metric["width_m"] == 3.6
    assert unlabelled["length_m"] is None
    assert unlabelled["width_m"] is None
    bare_value = parse_single_measurement("3200")
    assert bare_value["value"] == 3200
    assert bare_value["unit"] == "unknown"
    assert bare_value["value_m"] is None


def test_parse_feet_and_inches():
    result = parse_dimension_pair("12'-6\" x 10'-0\"")

    assert result is not None
    assert result["length_m"] == 3.81
    assert result["width_m"] == 3.048


def test_parse_space_delimited_feet_and_inches():
    result = parse_dimension_pair("12' 6\" x 10' 0\"")

    assert result is not None
    assert result["length_m"] == 3.81
    assert result["width_m"] == 3.048


def test_rotated_ocr_boxes_map_back_to_original_coordinates(monkeypatch):
    class FakeResult:
        def __init__(self, boxes, txts, scores):
            self.boxes = np.asarray(boxes, dtype=np.float32)
            self.txts = txts
            self.scores = scores

    class FakeEngine:
        def __init__(self):
            self.calls = 0

        def __call__(self, image):
            self.calls += 1
            if self.calls == 1:
                # At 90 degrees CCW this box maps to x=10..30, y=20..40.
                box = [[20, 170], [40, 170], [40, 190], [20, 190]]
                return FakeResult([box], ["BEDROOM"], [0.9])
            return FakeResult([], [], [])

    import ocr_room_labels
    monkeypatch.setattr(ocr_room_labels, "_rapid_ocr_engine", FakeEngine())
    image = Image.new("RGB", (200, 100), "white")

    items = extract_text_with_rapidocr(image)

    assert items[0]["selected_page_rotation"] == 90
    assert min(p[0] for p in items[0]["bbox"]) == 10
    assert max(p[0] for p in items[0]["bbox"]) == 30
    assert min(p[1] for p in items[0]["bbox"]) == 20
    assert max(p[1] for p in items[0]["bbox"]) == 40


def test_attach_room_name_and_printed_dimensions_by_polygon_overlap():
    rooms = [{"id": 1, "polygon": [[0, 0], [100, 0], [100, 100], [0, 100]]}]
    text_items = [
        {"text": "BEDROOM 1", "bbox": [[30, 30], [70, 30], [70, 40], [30, 40]], "confidence": 0.95},
        {"text": "3.60 x 4.20 m", "bbox": [[30, 50], [70, 50], [70, 60], [30, 60]], "confidence": 0.90},
        {"text": "KITCHEN", "bbox": [[120, 30], [170, 30], [170, 40], [120, 40]], "confidence": 0.99},
    ]

    enriched = attach_ocr_to_rooms(rooms, text_items)

    assert enriched[0]["room_name"] == "BEDROOM 1"
    assert len(enriched[0]["printed_dimensions"]) == 1
    assert enriched[0]["printed_dimensions"][0]["length_m"] == 4.2
    assert len(enriched[0]["ocr_text"]) == 2


def test_native_pdf_text_extracts_room_name_and_dimensions_with_pixel_boxes():
    import pymupdf

    document = pymupdf.open()
    page = document.new_page(width=200, height=100)
    page.insert_text((20, 30), "BEDROOM 1")
    page.insert_text((20, 60), "3.60 x 4.20 m")
    pdf_bytes = document.tobytes()
    document.close()

    text_items = extract_pdf_text_items(pdf_bytes, image_size=(400, 200))
    rooms = [{"id": 1, "polygon": [[0, 0], [400, 0], [400, 200], [0, 200]]}]
    enriched = attach_ocr_to_rooms(rooms, text_items)

    assert [item["text"] for item in text_items] == ["BEDROOM 1", "3.60 x 4.20 m"]
    assert text_items[0]["source"] == "pdf_text"
    assert max(point[0] for point in text_items[0]["bbox"]) > 40
    assert enriched[0]["room_name"] == "BEDROOM 1"
    assert enriched[0]["printed_dimensions"][0]["length_m"] == 4.2


def test_native_text_wins_duplicate_ocr_without_dropping_distant_same_text():
    native = [{
        "text": "BEDROOM",
        "bbox": [[10, 10], [60, 10], [60, 20], [10, 20]],
        "confidence": 1.0,
        "source": "pdf_text",
    }]
    ocr = [
        {"text": " BEDROOM ", "bbox": [[11, 10], [61, 10], [61, 20], [11, 20]]},
        {"text": "BEDROOM", "bbox": [[200, 10], [250, 10], [250, 20], [200, 20]]},
    ]

    merged = merge_text_items(native, ocr)

    assert len(merged) == 2
    assert merged[0]["source"] == "pdf_text"


def test_commercial_room_name_is_paired_with_dimension():
    rooms = [{"id": 1, "polygon": [[0, 0], [100, 0], [100, 100], [0, 100]]}]
    text_items = [
        {"text": "MEETING ROOM 2", "bbox": [[20, 20], [80, 20], [80, 30], [20, 30]]},
        {"text": "7200 x 5400 mm", "bbox": [[20, 40], [80, 40], [80, 50], [20, 50]]},
    ]

    enriched = attach_ocr_to_rooms(rooms, text_items)

    assert enriched[0]["room_name"] == "MEETING ROOM 2"
    assert enriched[0]["printed_dimensions"][0]["length_m"] == 7.2
    assert enriched[0]["printed_dimensions"][0]["width_m"] == 5.4