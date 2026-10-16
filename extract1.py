<<<<<<< HEAD
from header import header
import pymupdf


doc = pymupdf.open("Floorplan.pdf")
for page in doc:
    page.insert_text((50, 50), header)
    page.insert_text((50, page.rect.height - 50), "Footer")
    # insert footer 50 points above page bottom

import sys, pathlib, pymupdf
fname = sys.argv[1]
with pymupdf.open(fname) as doc:
    text = chr (12).join([page.get_text() for page in doc])
pathlib.Path(fname + ".text").write_bytes(text.encode())

import sys
import pymupdf


def mark_word(page, text):
    found = 0
    wlist = page.get_text("words", delimiters = None)
    for w in wlist:
        if text in w[4]:
            found += 1
        r = pymupdf.Rect(w[:4])
        page.add_underline_annot(r)
    return found

fname = sys.argv[1]
text = sys.argv[2]
doc = pymupdf.open(fname)
print (f"underlining words containing '{text}'in document '{doc.name}'")
new_doc = False 
for page in doc:
    found = mark_word(page, text)
    if found:
        new_doc = True
        print(f"found '{text}' {found} times on page {page.number + 1}")
if new_doc:
    doc.save("marked-" + doc.name)


# How to Mark Searched Text
import pymupdf
doc = pymupdf.open()
needle  = "Kitchen""
page = doc[0]
rl = page.search_for(needle, quads = True)
page.add_squiggly_annot(rl)
doc.save("a-squiggly.pdf")
=======
from header import header
import pymupdf


doc = pymupdf.open("Floorplan.pdf")
for page in doc:
    page.insert_text((50, 50), header)
    page.insert_text((50, page.rect.height - 50), "Footer")
    # insert footer 50 points above page bottom

import sys, pathlib, pymupdf
fname = sys.argv[1]
with pymupdf.open(fname) as doc:
    text = chr (12).join([page.get_text() for page in doc])
pathlib.Path(fname + ".text").write_bytes(text.encode())

import sys
import pymupdf


def mark_word(page, text):
    found = 0
    wlist = page.get_text("words", delimiters = None)
    for w in wlist:
        if text in w[4]:
            found += 1
        r = pymupdf.Rect(w[:4])
        page.add_underline_annot(r)
    return found

fname = sys.argv[1]
text = sys.argv[2]
doc = pymupdf.open(fname)
print (f"underlining words containing '{text}'in document '{doc.name}'")
new_doc = False 
for page in doc:
    found = mark_word(page, text)
    if found:
        new_doc = True
        print(f"found '{text}' {found} times on page {page.number + 1}")
if new_doc:
    doc.save("marked-" + doc.name)


# How to Mark Searched Text
import pymupdf
doc = pymupdf.open()
needle  = "Kitchen""
page = doc[0]
rl = page.search_for(needle, quads = True)
page.add_squiggly_annot(rl)
doc.save("a-squiggly.pdf")

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
>>>>>>> 7916fd5 (refine)
