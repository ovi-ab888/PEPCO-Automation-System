"""
hangtag_pad.py
===============
PEPCO Hangtag — Pad compositing: 1x Front + 7x Back (same back, repeated)
composited onto the Pad template, plus the Pad header fields (shared
8-field style: Order_ID, Item_classification, Style, Colour, Designer,
Dept, and the top-right COLOUR swatch name).

Position config lives in config/hangtag_pad_mapping.json — same pattern
as hangtag_front.py / hangtag_back.py.

Repo structure needed:
    labels/hangtag_pad.py     (this file)
    labels/hangtag_front.py
    labels/hangtag_back.py
    config/hangtag_pad_mapping.json
    fonts/ArialRegular.ttf
    templates/Hangtag/pad.pdf   <- your cleaned Pad template

Note: Tech Pack Rcvd / Last Revision Date / Final Approved Date /
Customer stay BLANK on the Pad (confirmed earlier — manual fields, not
data-driven). Buyer/Product/Measurement are fixed template text.
"""

import fitz  # PyMuPDF
import json
import os

from labels import hangtag_front as hf
from labels import hangtag_back as hb

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "Hangtag", "pad.pdf")
CONFIG_PATH = os.path.join(BASE_DIR, "config", "hangtag_pad_mapping.json")
TAHOMA_FONT_PATH = os.path.join(BASE_DIR, "fonts", "Tahoma.ttf")

BLACK = (0, 0, 0, 1)  # CMYK C0 M0 Y0 K100 - print-safe pure black

fitz.TOOLS.set_aa_level(0)  # keep barcode preview scannable, same as hangtag_back.py


def load_mapping(config_path=CONFIG_PATH):
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def fill_pad_header(page, row, mapping):
    """
    Fill the Pad header fields directly on the (already-opened) pad page.
    `mapping["header"]` is a list of field configs (matches the shared
    system's pad_header_mapping.json format):
        {"name": "Order_ID", "type": "text", "x": 97, "y": 132,
         "font_size": 9, "font": "tahoma", "prefix": ""}
    """
    fontname = "helv"
    if os.path.exists(TAHOMA_FONT_PATH):
        page.insert_font(fontfile=TAHOMA_FONT_PATH, fontname="tahoma")
        fontname = "tahoma"

    for field in mapping.get("header", []):
        value = row.get(field["name"], "")
        if value:
            text = f"{field.get('prefix', '')}{value}"
            page.insert_text((field["x"], field["y"]), text, fontsize=field["font_size"],
                              fontname=fontname, color=BLACK)


def generate_pad_repeat_back(row, front_bytes=None, back_bytes=None, template_path=TEMPLATE_PATH,
                              config_path=CONFIG_PATH, mapping=None):
    """
    Old behaviour: 1 Front + the SAME Back repeated 7 times. Kept for
    cases where you genuinely want 7 identical copies of one unit. For
    real order data (multiple units/barcodes sharing one style+price),
    use generate_pad_for_group() / generate_batch() instead.
    """
    if mapping is None:
        mapping = load_mapping(config_path)
    if front_bytes is None:
        front_bytes = hf.generate_single(row)
    if back_bytes is None:
        back_bytes = hb.generate_single(row)

    pad_doc = fitz.open(template_path)
    pad_page = pad_doc[0]
    fill_pad_header(pad_page, row, mapping)

    front_src = fitz.open("pdf", front_bytes)
    pad_page.show_pdf_page(fitz.Rect(mapping["front_rect"]), front_src, 0)
    front_src.close()

    back_src = fitz.open("pdf", back_bytes)
    for rect_coords in mapping["back_rects"]:
        pad_page.show_pdf_page(fitz.Rect(rect_coords), back_src, 0)
    back_src.close()

    data = pad_doc.tobytes()
    pad_doc.close()
    return data


# Backward-compat alias (old name).
generate_pad = generate_pad_repeat_back


_FRONT_KEY_COLUMNS = ["product_name", "EUR", "BAM", "PLN", "RON", "CZK", "MKD", "RSD", "HUF"]


def _front_signature(row):
    """Rows with the same product_name + price set share one Front side."""
    return tuple(row.get(col, "") for col in _FRONT_KEY_COLUMNS)


def group_rows_for_pads(rows, chunk_size=None, mapping=None):
    """
    Groups rows into Pad-sized chunks: consecutive rows that share the same
    Front signature (same product_name + prices) go on the same Pad, up to
    `chunk_size` rows per Pad — each row becomes ONE Back slot with its
    own barcode/SKU/batch, while the Front is generated ONCE per group
    (from the group's first row). A signature change always starts a new
    group, even if the current group has fewer rows than chunk_size yet.

    `chunk_size` defaults to however many Back slots the Pad template
    actually has (len(mapping["back_rects"])) — so a template variant with
    8 Back slots instead of 7 is picked up automatically, no code change
    needed. Pass `mapping` (or rely on the default CONFIG_PATH) so this can
    be computed; an explicit `chunk_size` always overrides it.
    """
    if chunk_size is None:
        if mapping is None:
            mapping = load_mapping()
        chunk_size = len(mapping["back_rects"])

    groups = []
    current = []
    current_key = None
    for row in rows:
        key = _front_signature(row)
        if current and (key != current_key or len(current) >= chunk_size):
            groups.append(current)
            current = []
        current.append(row)
        current_key = key
    if current:
        groups.append(current)
    return groups


def generate_pad_for_group(group_rows, template_path=TEMPLATE_PATH, config_path=CONFIG_PATH, mapping=None):
    """
    Build ONE Pad PDF (bytes) for a group of 1-7 rows: ONE Front (from
    group_rows[0]) + up to 7 Back slots, each filled with a DIFFERENT row's
    data (different barcode/SKU/batch/etc per unit). Leftover Back slots
    (if the group has fewer than 7 rows) are left blank.
    """
    if mapping is None:
        mapping = load_mapping(config_path)
    if not group_rows:
        raise ValueError("group_rows is empty")
    if len(group_rows) > len(mapping["back_rects"]):
        raise ValueError(
            f"This Pad template only has {len(mapping['back_rects'])} Back slots, "
            f"got {len(group_rows)} rows in this group"
        )

    header_row = group_rows[0]
    front_bytes = hf.generate_single(header_row)

    pad_doc = fitz.open(template_path)
    pad_page = pad_doc[0]
    fill_pad_header(pad_page, header_row, mapping)

    front_src = fitz.open("pdf", front_bytes)
    pad_page.show_pdf_page(fitz.Rect(mapping["front_rect"]), front_src, 0)
    front_src.close()

    for rect_coords, unit_row in zip(mapping["back_rects"], group_rows):
        back_bytes = hb.generate_single(unit_row)
        back_src = fitz.open("pdf", back_bytes)
        pad_page.show_pdf_page(fitz.Rect(rect_coords), back_src, 0)
        back_src.close()
    # Remaining back_rects (if group has < 7 rows) are simply left blank —
    # the template's own empty box shows there, matching a partial pad.

    data = pad_doc.tobytes()
    pad_doc.close()
    return data


def generate_batch(rows, template_path=TEMPLATE_PATH, config_path=CONFIG_PATH):
    """
    Groups `rows` (same product_name+price -> same Pad, one unique Back
    per row, up to however many Back slots the template has) and returns
    a list of Pad PDF bytes, one per Pad/group.
    """
    mapping = load_mapping(config_path)
    groups = group_rows_for_pads(rows, mapping=mapping)
    return [generate_pad_for_group(g, template_path=template_path, mapping=mapping) for g in groups]


def generate_batch_pdf(rows, template_path=TEMPLATE_PATH, config_path=CONFIG_PATH):
    """Same grouping as generate_batch(), but returns ONE multi-page PDF (one Pad page per group)."""
    mapping = load_mapping(config_path)
    groups = group_rows_for_pads(rows, mapping=mapping)
    out = fitz.open()
    for g in groups:
        pad_bytes = generate_pad_for_group(g, template_path=template_path, mapping=mapping)
        pad_single = fitz.open("pdf", pad_bytes)
        out.insert_pdf(pad_single)
        pad_single.close()
    data = out.tobytes()
    out.close()
    return data
