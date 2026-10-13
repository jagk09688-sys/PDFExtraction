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
