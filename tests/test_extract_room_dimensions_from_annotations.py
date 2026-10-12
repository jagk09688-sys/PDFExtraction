import json
from pathlib import Path

from PIL import Image

from extract_room_dimensions_from_annotations import process_annotation_file
from validate_annotations import validate_page


def _official_annotation(**overrides):
    annotation = {
        "page_number": 1,
        "image_width": 100,
        "image_height": 100,
        "source_pdf": "sample.pdf",
        "annotator": "reviewer",
        "timestamp": "2026-01-01T00:00:00Z",
        "rooms": [
            {
                "id": "P01-R01",
                "polygon": [[10, 10], [10, 90], [90, 90], [90, 10]],
                "label": "Living",
                "material": "carpet",
            }
        ],
        "dimensions": [
            {
                "text": "5.2 m",
                "value": 5.2,
                "bbox": [10, 1, 20, 5],
                "associated_room": "P01-R01",
                "type": "length",
                "unit": "m",
            },
            {
                "text": "3.0 m",
                "value": 3.0,
                "bbox": [1, 10, 5, 20],
                "associated_room": "P01-R01",
                "type": "width",
                "unit": "m",
            },
        ],
        "text_labels": [],
        "structural_elements": [],
        "table_rows": [],
    }
    annotation.update(overrides)
    return annotation


def test_official_annotations_export_confirmed_dimensions_and_material(tmp_path: Path):
    annotation_path = tmp_path / "page_001.json"
    annotation_path.write_text(json.dumps(_official_annotation()), encoding="utf-8")

    rooms = process_annotation_file(annotation_path)

    assert len(rooms) == 1
    room = rooms[0]
    assert room["id"] == "P01-R01"
    assert room["length_m"] == 5.2
    assert room["width_m"] == 3.0
    assert room["area_m2"] == 15.6
    assert room["material_type"] == "carpet"
    assert room["carpet_required_4_0_m"] == 5.2
    assert len(room["annotated_dimensions"]) == 2


def test_unscaled_or_unitless_annotations_do_not_invent_metres(tmp_path: Path):
    annotation = _official_annotation(
        dimensions=[
            {
                "text": "5200",
                "value": 5200,
                "bbox": [10, 1, 20, 5],
                "associated_room": "P01-R01",
                "type": "length",
            },
            {
                "text": "3000",
                "value": 3000,
                "bbox": [1, 10, 5, 20],
                "associated_room": "P01-R01",
                "type": "width",
            },
        ]
    )
    annotation_path = tmp_path / "page_001.json"
    annotation_path.write_text(json.dumps(annotation), encoding="utf-8")

    room = process_annotation_file(annotation_path)[0]

    assert room["length_m"] is None
    assert room["width_m"] is None
    assert room["area_m2"] is None
    assert room["carpet_required_4_0_m"] is None


def test_legacy_labelme_requires_explicit_scale_and_unknown_material_is_not_guessed(tmp_path: Path):
    annotation_path = tmp_path / "legacy.json"
    annotation_path.write_text(
        json.dumps({
            "imageHeight": 100,
            "imageWidth": 100,
            "shapes": [{
                "label": "Meeting room",
                "points": [[10, 10], [10, 90], [90, 90], [90, 10]],
            }],
        }),
        encoding="utf-8",
    )

    room = process_annotation_file(annotation_path)[0]

    assert room["length_m"] is None
    assert room["area_m2"] is None
    assert room["material_type"] == "unknown"
    assert room["carpet_required_4_0_m"] is None


def test_official_annotation_validator_accepts_units_and_rejects_unknown_units(tmp_path: Path):
    project_dir = tmp_path / "project"
    annotations_dir = project_dir / "annotations"
    pages_dir = project_dir / "pages"
    annotations_dir.mkdir(parents=True)
    pages_dir.mkdir()
    Image.new("RGB", (100, 100), color="white").save(pages_dir / "page_001.png")

    annotation_path = annotations_dir / "page_001.json"
    annotation_path.write_text(json.dumps(_official_annotation()), encoding="utf-8")
    assert validate_page(annotation_path) == []

    annotation = _official_annotation()
    annotation["dimensions"][0]["unit"] = "yards"
    annotation_path.write_text(json.dumps(annotation), encoding="utf-8")
    errors = validate_page(annotation_path)
    assert any("dimensions[0].unit" in error for error in errors)
