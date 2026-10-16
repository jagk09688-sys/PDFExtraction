<<<<<<< HEAD
import re
import fitz  # PyMuPDF


def extract_dimensions_from_pdf(pdf_path):
    # Open the PDF document
    doc = fitz.open(pdf_path)

    # Common regex patterns for room dimensions
    # Pattern 1: Feet and inches (e.g., 12'-6" x 10'-0" or 12'6" x 10'0")
    feet_inches_pattern = re.compile(
        r"\b\d+[-']\d*\"?\s*[xX×]\s*\d+[-']\d*\"?\b"
    )

    # Pattern 2: Metric or standard decimals (e.g., 3.5 x 4.2, 12.5x14, 4.0m x 3.2m)
    decimal_pattern = re.compile(
        r"\b\d+(?:\.\d+)?(?:m)?\s*[xX×]\s*\d+(?:\.\d+)?(?:m)?\b"
    )

    found_dimensions = {}

    # Iterate through all pages
    for page_num in range(len(doc)):
        page = doc[page_num]
        # Extract text blocks to help keep room names and dimensions together
        text_blocks = page.get_text("blocks")

        for block in text_blocks:
            block_text = block[4]  # The text content of the block

            # Clean up newlines for easier regex matching
            clean_text = " ".join(block_text.split())

            # Search for matches
            matches = feet_inches_pattern.findall(
                clean_text
            ) + decimal_pattern.findall(clean_text)

            if matches:
                # Try to capture the surrounding text (likely the room name like "Bedroom")
                found_dimensions[clean_text] = matches

    return found_dimensions


# Example Usage:
# pdf_file = "floor_plan.pdf"
# results = extract_dimensions_from_pdf(pdf_file)
# for text, dimensions in results.items():
#     print(f"Found: {dimensions} in context: '{text}'")
=======
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
>>>>>>> 7916fd5 (refine)
