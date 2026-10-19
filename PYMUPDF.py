"""Extract printed room-dimension pairs from searchable PDF text."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import TypeAlias

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # Older PyMuPDF releases expose this module name.


_NUMBER = r"\d+(?:[.,]\d+)?"
_MEASURE = (
    rf"{_NUMBER}\s*(?:(?:'\s*(?:-?\s*{_NUMBER}\s*(?:\"|in)?)?)|"
    rf"(?:mm|cm|m|ft|in|\"))?"
)
_DIMENSION_PATTERN = re.compile(
    rf"(?<![\w.]){_MEASURE}\s*[xX×]\s*{_MEASURE}(?![\w.])",
    re.IGNORECASE,
)

DimensionResults: TypeAlias = dict[str, list[str]]


def extract_dimensions_from_pdf(pdf_path: str | Path) -> DimensionResults:
    """Return dimension pairs grouped by their normalized text-block context.

    Supports decimal/comma-decimal values, common metric and imperial units,
    and feet/inches forms such as ``12'-6\" x 10'-0\"``. The return type keeps
    the original ``{context: [dimension, ...]}`` interface.
    """
    found_dimensions: DimensionResults = {}

    # The context manager ensures the PDF is closed even if text extraction fails.
    with fitz.open(pdf_path) as document:
        for page in document:
            for block in page.get_text("blocks"):
                if len(block) <= 4 or not isinstance(block[4], str):
                    continue

                context = " ".join(block[4].split())
                if not context:
                    continue

                matches = [match.group(0).strip() for match in _DIMENSION_PATTERN.finditer(context)]
                if matches:
                    # Keep repeated contexts from different blocks/pages instead
                    # of silently overwriting earlier dimensions.
                    found_dimensions.setdefault(context, []).extend(matches)

    return found_dimensions


def main() -> None:
    """Print extracted dimensions as JSON for command-line use."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="PDF file with selectable text")
    args = parser.parse_args()
    print(json.dumps(extract_dimensions_from_pdf(args.pdf), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
