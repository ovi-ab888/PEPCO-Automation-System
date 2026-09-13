"""
hangtag_back.py
================
PEPCO Hangtag — BACK SIDE only.

Position/font config lives in config/hangtag_back_mapping.json — same
pattern as hangtag_front.py / pad_header_mapping.json.

Repo structure needed:
    labels/hangtag_back.py   (this file)
    config/hangtag_back_mapping.json
    fonts/ArialRegular.ttf
    fonts/PEPCO_Ovi.ttf        (pictogram font — washing_code + Cotton)
    templates/Hangtag/back_side.pdf   <- your cleaned template

Coordinates are in PDF points, TOP-LEFT origin (PyMuPDF convention).
Page size: 130.89 x 326.48 pt (46.2mm x 115.2mm) — same as front side.
"""

import fitz  # PyMuPDF
import json
import os

# Disable anti-aliasing for rasterization (get_pixmap previews). This has
# ZERO effect on the actual vector PDF output (which was always correct) —
# it only fixes preview PNGs so a barcode scanner can read them too, by
# avoiding the sub-pixel edge blur that antialiasing introduces.
fitz.TOOLS.set_aa_level(0)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "Hangtag", "back_side.pdf")
CONFIG_PATH = os.path.join(BASE_DIR, "config", "hangtag_back_mapping.json")
ARIAL_FONT_PATH = os.path.join(BASE_DIR, "fonts", "ArialRegular.ttf")
PICTOGRAM_FONT_PATH = os.path.join(BASE_DIR, "fonts", "PEPCO_Ovi.ttf")

BRAND_PINK = (236 / 255, 0 / 255, 140 / 255)   # #EC008C
BLACK = (0, 0, 0, 1)                           # CMYK C0 M0 Y0 K100 - print-safe pure black

COLOR_MAP = {"black": BLACK, "pink": BRAND_PINK}

# --- Sample data to preview with ---
SAMPLE_ROW = {
    "Collection": "MODERN 1",
    "Colour_SKU": "BLACK • SKU 12345678",
    "Style_Merch_Season": "STYLE 123456 • ABC12027 • Batch No./",
    "Batch": "виготовлення: 072026",
    "washing_code": "gjnqt",
    "Cotton": "Z",
    "barcode": "2200164366761",
}


def load_mapping(config_path=CONFIG_PATH):
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _insert_text(page, text, bbox, fontsize, color=BLACK, fontname="helv", align="left",
                  fontfile=None, fontbuffer=None):
    if not text:
        return
    rect = fitz.Rect(bbox)
    text = str(text)
    if fontfile or fontbuffer:
        font_obj = fitz.Font(fontfile=fontfile, fontbuffer=fontbuffer)
    else:
        font_obj = fitz.Font(fontname=fontname)
    tw = font_obj.text_length(text, fontsize=fontsize)
    if align == "center":
        x = rect.x0 + (rect.width - tw) / 2
    elif align == "right":
        x = rect.x1 - tw
    else:
        x = rect.x0
    y = rect.y1 - (rect.height - fontsize) / 2 - 1
    page.insert_text((x, y), text, fontsize=fontsize, fontname=fontname, color=color)


def _draw_ean13(page, code, x0, x1, y_bars_bottom, bars_height, color=BRAND_PINK):
    """Self-contained standard EAN13 vector bar renderer (guard/L/G/R pattern)."""
    L_CODES = {
        '0': '0001101', '1': '0011001', '2': '0010011', '3': '0111101', '4': '0100011',
        '5': '0110001', '6': '0101111', '7': '0111011', '8': '0110111', '9': '0001011',
    }
    G_CODES = {
        '0': '0100111', '1': '0110011', '2': '0011011', '3': '0100001', '4': '0011101',
        '5': '0111001', '6': '0000101', '7': '0010001', '8': '0001001', '9': '0010111',
    }
    R_CODES = {k: ''.join('1' if c == '0' else '0' for c in v) for k, v in L_CODES.items()}
    PARITY = {
        '0': 'LLLLLL', '1': 'LLGLGG', '2': 'LLGGLG', '3': 'LLGGGL', '4': 'LGLLGG',
        '5': 'LGGLLG', '6': 'LGGGLL', '7': 'LGLGLG', '8': 'LGLGGL', '9': 'LGGLGL',
    }
    code = str(code).zfill(13)
    first, rest = code[0], code[1:]
    left, right = rest[:6], rest[6:]
    parity = PARITY[first]

    bits = "101"
    for i, d in enumerate(left):
        bits += L_CODES[d] if parity[i] == 'L' else G_CODES[d]
    bits += "01010"
    for d in right:
        bits += R_CODES[d]
    bits += "101"

    total_width = x1 - x0
    module_w = total_width / len(bits)
    # All bars share the same TOP edge (standard barcode look). Guard bars
    # (start/middle/end) extend further DOWN toward the digit line; regular
    # data bars are shorter and stop above that — NOT the other way round
    # (extending upward), which is what made it look "flipped/rotated".
    y_top = y_bars_bottom - bars_height
    short_height = bars_height / 1.15
    for i, bit in enumerate(bits):
        is_guard = i < 3 or (45 <= i < 50) or i >= len(bits) - 3
        y_bottom_this_bar = y_top + (bars_height if is_guard else short_height)
        if bit == "1":
            bar_x0 = x0 + i * module_w
            bar_x1 = x0 + (i + 1) * module_w
            page.draw_rect(fitz.Rect(bar_x0, y_top, bar_x1, y_bottom_this_bar),
                            color=color, fill=color, width=0)


def fill_back_side(row, template_path=TEMPLATE_PATH, config_path=CONFIG_PATH, mapping=None,
                    arial_font_bytes=None, pictogram_font_bytes=None):
    """Returns a fitz.Document with the back side filled in."""
    if mapping is None:
        mapping = load_mapping(config_path)
    doc = fitz.open(template_path)
    page = doc[0]

    # --- Arial text fields: Collection, Colour_SKU, Style_Merch_Season, Batch ---
    arial_fontname = "helv"
    if arial_font_bytes:
        page.insert_font(fontbuffer=arial_font_bytes, fontname="arial_font")
        arial_fontname = "arial_font"
    elif os.path.exists(ARIAL_FONT_PATH):
        page.insert_font(fontfile=ARIAL_FONT_PATH, fontname="arial_font")
        arial_fontname = "arial_font"

    for field in ["Collection", "Colour_SKU", "Style_Merch_Season", "Batch"]:
        cfg = mapping.get(field)
        if cfg and row.get(field):
            color = COLOR_MAP.get(cfg.get("color", "black"), BLACK)
            _insert_text(page, row[field], cfg["bbox"], cfg["fontsize"], color=color,
                         fontname=arial_fontname, align=cfg.get("align", "center"),
                         fontfile=(ARIAL_FONT_PATH if arial_fontname == "arial_font" and not arial_font_bytes else None),
                         fontbuffer=arial_font_bytes if arial_fontname == "arial_font" else None)

    # --- Pictogram fields: washing_code, Cotton ---
    pictogram_fontname = "helv"
    if pictogram_font_bytes:
        page.insert_font(fontbuffer=pictogram_font_bytes, fontname="pictogram_font")
        pictogram_fontname = "pictogram_font"
    elif os.path.exists(PICTOGRAM_FONT_PATH):
        page.insert_font(fontfile=PICTOGRAM_FONT_PATH, fontname="pictogram_font")
        pictogram_fontname = "pictogram_font"

    for field in ["washing_code", "Cotton"]:
        cfg = mapping.get(field)
        if cfg and row.get(field):
            color = COLOR_MAP.get(cfg.get("color", "pink"), BRAND_PINK)
            _insert_text(page, row[field], cfg["bbox"], cfg["fontsize"], color=color,
                         fontname=pictogram_fontname, align=cfg.get("align", "left"),
                         fontfile=(PICTOGRAM_FONT_PATH if pictogram_fontname == "pictogram_font" and not pictogram_font_bytes else None),
                         fontbuffer=pictogram_font_bytes if pictogram_fontname == "pictogram_font" else None)

    # --- Barcode (EAN13 vector bars + human-readable digits) ---
    bc_cfg = mapping.get("barcode")
    barcode = str(row.get("barcode", "")).strip()
    if barcode.endswith(".0"):
        barcode = barcode[:-2]
    if bc_cfg and barcode and barcode.lower() != "nan":
        color = COLOR_MAP.get(bc_cfg.get("color", "pink"), BRAND_PINK)
        _draw_ean13(page, barcode, bc_cfg["x0"], bc_cfg["x1"],
                    bc_cfg["digits_y0"] - 2, bc_cfg["bars_height"], color=color)

        fs = bc_cfg["digits_fontsize"]
        y = bc_cfg["digits_y1"] - (bc_cfg["digits_y1"] - bc_cfg["digits_y0"] - fs) / 2 - 1
        # Illustrator-style "tracking": 100 = +0.1em extra space per
        # character (tracking/1000 * fontsize). Configurable via
        # bc_cfg["digits_tracking"] (defaults to 100 to match reference).
        tracking = bc_cfg.get("digits_tracking", 100) / 1000.0 * fs

        def _tracked_width(s):
            return fitz.get_text_length(s, fontname="helv", fontsize=fs) + tracking * max(len(s) - 1, 0)

        def _draw_tracked(s, x_start, y_pos):
            x = x_start
            for ch in s:
                page.insert_text((x, y_pos), ch, fontsize=fs, fontname="helv", color=color)
                x += fitz.get_text_length(ch, fontname="helv", fontsize=fs) + tracking

        if len(barcode) == 13:
            # Authentic EAN13 digit layout: 1st digit sits to the LEFT of
            # the bars (outside), then the two 6-digit groups sit centered
            # under the left half and right half of the bars respectively —
            # not one single centered string (which looks cramped/wrong).
            first_digit, left_group, right_group = barcode[0], barcode[1:7], barcode[7:]
            bars_mid = (bc_cfg["x0"] + bc_cfg["x1"]) / 2

            fd_w = _tracked_width(first_digit)
            _draw_tracked(first_digit, bc_cfg["x0"] - fd_w - 2, y)

            lg_w = _tracked_width(left_group)
            lg_x = bc_cfg["x0"] + (bars_mid - bc_cfg["x0"] - lg_w) / 2
            _draw_tracked(left_group, lg_x, y)

            rg_w = _tracked_width(right_group)
            rg_x = bars_mid + (bc_cfg["x1"] - bars_mid - rg_w) / 2
            _draw_tracked(right_group, rg_x, y)
        else:
            tw = _tracked_width(barcode)
            x = bc_cfg["x0"] + ((bc_cfg["x1"] - bc_cfg["x0"]) - tw) / 2
            _draw_tracked(barcode, x, y)

    return doc


def generate_single(row, template_path=TEMPLATE_PATH, config_path=CONFIG_PATH):
    doc = fill_back_side(row, template_path, config_path)
    data = doc.tobytes()
    doc.close()
    return data


def generate_batch(rows, template_path=TEMPLATE_PATH, config_path=CONFIG_PATH):
    return [generate_single(row, template_path, config_path) for row in rows]


def generate_batch_pdf(rows, template_path=TEMPLATE_PATH, config_path=CONFIG_PATH):
    """Returns ONE multi-page PDF (bytes), one page per row."""
    out = fitz.open()
    for row in rows:
        doc = fill_back_side(row, template_path, config_path)
        out.insert_pdf(doc)
        doc.close()
    data = out.tobytes()
    out.close()
    return data


if __name__ == "__main__":
    if not os.path.exists(TEMPLATE_PATH):
        print(f"❌ Template not found at: {TEMPLATE_PATH}")
    elif not os.path.exists(CONFIG_PATH):
        print(f"❌ Config not found at: {CONFIG_PATH}")
    else:
        doc = fill_back_side(SAMPLE_ROW)
        doc.save("preview_back.pdf")
        pix = doc[0].get_pixmap(dpi=200)
        pix.save("preview_back.png")
        doc.close()
        print("✅ Done — check preview_back.png (or preview_back.pdf)")
