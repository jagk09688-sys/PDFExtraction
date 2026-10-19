"""Compatibility command-line entry point for PDF dimension extraction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PYMUPDF import extract_dimensions_from_pdf


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="PDF file with selectable text")
    args = parser.parse_args()
    results = extract_dimensions_from_pdf(args.pdf)
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
