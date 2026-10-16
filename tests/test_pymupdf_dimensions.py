from unittest.mock import patch

from PYMUPDF import extract_dimensions_from_pdf


class FakePage:
    def __init__(self, *texts):
        self.texts = texts

    def get_text(self, kind):
        assert kind == "blocks"
        return [(0, 0, 1, 1, text) for text in self.texts]


class FakeDocument:
    def __init__(self, *pages):
        self.pages = pages
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.closed = True

    def __iter__(self):
        return iter(self.pages)


def test_extracts_supported_dimension_formats_and_normalizes_context():
    document = FakeDocument(
        FakePage(
            "Bedroom\n12'-6\" x 10'-0\"",
            "Kitchen 3,5 x 4,2 m; utility 250cm × 300cm",
            "Office 12'6\" x 10'0\"",
        )
    )
    with patch("PYMUPDF.fitz.open", return_value=document):
        result = extract_dimensions_from_pdf("plan.pdf")

    assert result == {
        'Bedroom 12\'-6" x 10\'-0"': ['12\'-6" x 10\'-0"'],
        "Kitchen 3,5 x 4,2 m; utility 250cm × 300cm": [
            "3,5 x 4,2 m",
            "250cm × 300cm",
        ],
        'Office 12\'6" x 10\'0"': ['12\'6" x 10\'0"'],
    }
    assert document.closed


def test_same_context_from_multiple_blocks_keeps_all_matches():
    document = FakeDocument(FakePage("Room 3 x 4", "Room 3 x 4"))
    with patch("PYMUPDF.fitz.open", return_value=document):
        result = extract_dimensions_from_pdf("plan.pdf")

    assert result == {"Room 3 x 4": ["3 x 4", "3 x 4"]}


def test_ignores_nonnumeric_and_embedded_number_strings():
    document = FakeDocument(FakePage("A2x3 code", "Room 3 x 4", "Scale 1:100"))
    with patch("PYMUPDF.fitz.open", return_value=document):
        result = extract_dimensions_from_pdf("plan.pdf")

    assert result == {"Room 3 x 4": ["3 x 4"]}
