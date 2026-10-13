"""
hangtag_front.py
=================
PEPCO Hangtag — FRONT SIDE only.

Position/font-size config lives in a JSON file (same pattern as
config/pad_header_mapping.json elsewhere in this project) — NOT
hardcoded in this file. Edit the JSON to adjust positions, no code
change needed.

HOW TO USE (manual position adjustment workflow):
1. Put your cleaned template at: templates/Hangtag/front_side.pdf
   (pink placeholder text removed, blank/clean template)
2. Edit config/hangtag_front_mapping.json (bbox / fontsize values).
3. Run:  python labels/hangtag_front.py   (from the repo root)
   -> Creates preview_front.pdf AND preview_front.png.
4. Repeat step 2-3 until the position looks right.

Coordinates are in PDF points, TOP-LEFT origin (PyMuPDF convention):
  x increases -> right,  y increases -> down.
  bbox = [x0, y0, x1, y1]  i.e. (left, top, right, bottom)
Page size for this template: 130.89 x 326.48 pt (46.2mm x 115.2mm)
"""

import fitz  # PyMuPDF (pip install pymupdf)
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "Hangtag", "front_side.pdf")
CONFIG_PATH = os.path.join(BASE_DIR, "config", "hangtag_front_mapping.json")

BRAND_PINK = (236 / 255, 0 / 255, 140 / 255)   # #EC008C - price numbers
BLACK = (35 / 255, 31 / 255, 32 / 255)         # #231F20 - body text

COLOR_MAP = {"black": BLACK, "pink": BRAND_PINK}


def load_mapping(config_path=CONFIG_PATH):
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


# --- Sample data to preview with (change freely while testing) ---
SAMPLE_ROW = {
    "product_name": (
        "|EN| Girls t-shirt |AL| T-shirt vajzash: 100% Pambuk |BG| Момичешка тениска "
        "|BiH| T-shirt za djevojčice. Sastav materijala na ušivenoj etiketi. "
        "|CZ| Dívčí t-shirt |DE| T-Shirt für Mädchen |EE| Tüdrukute T-särk"
    ),
    "EUR": "2,00", "BAM": "4,00", "PLN": "8,00", "RON": "9,00",
    "CZK": "50", "MKD": "120", "RSD": "250", "HUF": "750",
}


def _insert_right_aligned(page, text, bbox, fontsize, color=BRAND_PINK, fontname="helv"):
    if not text:
        return
    rect = fitz.Rect(bbox)
    tw = fitz.get_text_length(str(text), fontname=fontname, fontsize=fontsize)
    x = rect.x1 - tw
    y = rect.y1 - (rect.height - fontsize) / 2 - 1
    page.insert_text((x, y), str(text), fontsize=fontsize, fontname=fontname, color=color)


def fill_front_side(row, template_path=TEMPLATE_PATH, config_path=CONFIG_PATH):
    """Returns a fitz.Document with the front side filled in."""
    mapping = load_mapping(config_path)
    doc = fitz.open(template_path)
    page = doc[0]

    pn_cfg = mapping.get("product_name")
    if pn_cfg and row.get("product_name"):
        rect = fitz.Rect(pn_cfg["bbox"])
        color = COLOR_MAP.get(pn_cfg.get("color", "black"), BLACK)
        page.insert_textbox(rect, row["product_name"], fontsize=pn_cfg["fontsize"],
                             fontname="helv", color=color, align=0)

    for col, field_cfg in mapping.get("prices", {}).items():
        value = row.get(col, "")
        if value:
            _insert_right_aligned(page, value, field_cfg["bbox"], field_cfg["fontsize"])

    return doc


def generate_single(row, template_path=TEMPLATE_PATH, config_path=CONFIG_PATH):
    """Returns front-side PDF bytes for one row (use this from your app)."""
    doc = fill_front_side(row, template_path, config_path)
    data = doc.tobytes()
    doc.close()
    return data


def generate_batch(rows, template_path=TEMPLATE_PATH, config_path=CONFIG_PATH):
    """Returns a list of front-side PDF bytes, one per row."""
    return [generate_single(row, template_path, config_path) for row in rows]


def generate_batch_pdf(rows, template_path=TEMPLATE_PATH, config_path=CONFIG_PATH):
    """Returns ONE multi-page PDF (bytes), one page per row — matches the
    shared label_options["generate"](rows) -> pdf_bytes contract used by
    app.py / the main label-automation system (same as pad_label,
    inner_label, etc.)."""
    out = fitz.open()
    for row in rows:
        doc = fill_front_side(row, template_path, config_path)
        out.insert_pdf(doc)
        doc.close()
    data = out.tobytes()
    out.close()
    return data


if __name__ == "__main__":
    if not os.path.exists(TEMPLATE_PATH):
        print(f"❌ Template not found at: {TEMPLATE_PATH}")
        print("   Put your cleaned front_side.pdf there first, then rerun.")
    elif not os.path.exists(CONFIG_PATH):
        print(f"❌ Config not found at: {CONFIG_PATH}")
    else:
        doc = fill_front_side(SAMPLE_ROW)
        doc.save("preview_front.pdf")
        pix = doc[0].get_pixmap(dpi=200)
        pix.save("preview_front.png")
        doc.close()
        print("✅ Done — check preview_front.png (or preview_front.pdf)")
        print("   Adjust config/hangtag_front_mapping.json and rerun to fine-tune.")
