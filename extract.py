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
