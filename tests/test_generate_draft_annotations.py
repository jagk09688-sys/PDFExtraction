from generate_draft_annotations import _dimension_annotations


def test_dimension_candidates_are_exported_with_room_and_schema_fields():
    room = {
        "id": "P01-R02",
        "printed_dimensions": [
            {
                "text": "7200 x 12000 mm",
                "length_m": 12.0,
                "width_m": 7.2,
                "values": [12000, 7200],
                "bbox": [[10, 20], [50, 20], [50, 30], [10, 30]],
            }
        ],
    }

    dimensions = _dimension_annotations(room)

    assert dimensions == [
        {
            "text": "7200 x 12000 mm",
            "value": 12.0,
            "bbox": [10, 20, 50, 30],
            "associated_room": "P01-R02",
            "type": "length",
            "unit": "m",
        },
        {
            "text": "7200 x 12000 mm",
            "value": 7.2,
            "bbox": [10, 20, 50, 30],
            "associated_room": "P01-R02",
            "type": "width",
            "unit": "m",
        },
    ]


def test_unitless_draft_dimensions_stay_unscaled_and_unknown():
    room = {
        "id": "P01-R01",
        "printed_dimensions": [
            {
                "text": "7200 x 5400",
                "length_m": None,
                "width_m": None,
                "values": [7200, 5400],
                "bbox": [[10, 20], [50, 20], [50, 30], [10, 30]],
            }
        ],
    }

    dimensions = _dimension_annotations(room)

    assert [item["value"] for item in dimensions] == [7200, 5400]
    assert all(item["unit"] == "unknown" for item in dimensions)
