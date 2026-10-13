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

# All fonts are bundled in the repo's fonts/ folder — no upload needed.
ARIAL_FONT_PATH = os.path.join(BASE_DIR, "fonts", "ArialRegular.ttf")
BOLD_FONT_PATH = os.path.join(BASE_DIR, "fonts", "ArialBold.ttf")
MYRIADPRO_FONT_PATH = os.path.join(BASE_DIR, "fonts", "MyriadProSemibold.otf")
UNICODE_FONT_PATH = ARIAL_FONT_PATH  # kept as an alias for older code paths

BRAND_PINK = (236 / 255, 0 / 255, 140 / 255)   # #EC008C - price numbers
BLACK = (0, 0, 0, 1)                           # CMYK C0 M0 Y0 K100 - print-safe pure black

COLOR_MAP = {"black": BLACK, "pink": BRAND_PINK}
ALIGN_MAP = {"left": 0, "center": 1, "right": 2, "justify": 3}


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


import re

_COUNTRY_CODE_RE = re.compile(r"^\|[A-Za-z]{2,4}\|$")


def _wrap_and_justify_textbox(page, rect, text, fontsize, fontname, color, align="justify",
                               fontfile=None, fontbuffer=None, lineheight=1.15,
                               bold_fontname=None, bold_fontfile=None, bold_fontbuffer=None):
    """
    Custom paragraph renderer that properly justifies text with an
    EMBEDDED/custom font. PyMuPDF's own page.insert_textbox(..., align=3)
    only computes correct justify spacing for the base-14 fonts (e.g.
    "helv") — with a custom TTF/OTF loaded via insert_font, it silently
    falls back to left-aligned-looking output (ragged right edge). This
    function does word-wrap + justify manually using real glyph widths
    from a fitz.Font object, so it works correctly with ANY font.

    Tokens that look like a language/country code — "|EN|", "|BiH|",
    "|UA|" etc. (pipe, 2-4 letters, pipe) — are rendered in `bold_fontname`
    instead of the regular font, matching the reference design where each
    language tag is bold and the translation text after it is regular.

    Returns True if the text fit within rect.height at this fontsize.
    """
    font_obj = fitz.Font(fontfile=fontfile, fontbuffer=fontbuffer) if (fontfile or fontbuffer) \
        else fitz.Font(fontname=fontname)

    use_bold = bool(bold_fontname and (bold_fontfile or bold_fontbuffer))
    bold_font_obj = None
    if use_bold:
        bold_font_obj = fitz.Font(fontfile=bold_fontfile, fontbuffer=bold_fontbuffer)

    # Make sure this page can actually render these fonts — insert_text
    # requires each font to be registered on THIS specific page first.
    if fontfile or fontbuffer:
        page.insert_font(fontname=fontname, fontfile=fontfile, fontbuffer=fontbuffer)
    if use_bold:
        page.insert_font(fontname=bold_fontname, fontfile=bold_fontfile, fontbuffer=bold_fontbuffer)

    def _word_font(word):
        return bold_font_obj if (use_bold and _COUNTRY_CODE_RE.match(word)) else font_obj

    def _word_fontname(word):
        return bold_fontname if (use_bold and _COUNTRY_CODE_RE.match(word)) else fontname

    space_w = font_obj.text_length(" ", fontsize=fontsize)
    words = text.split()
    box_width = rect.width
    line_gap = fontsize * lineheight

    lines = []  # list of list-of-words
    current = []
    current_w = 0.0
    for word in words:
        w = _word_font(word).text_length(word, fontsize=fontsize)
        added_w = w if not current else w + space_w
        if current and current_w + added_w > box_width:
            lines.append(current)
            current = [word]
            current_w = w
        else:
            current.append(word)
            current_w += added_w
    if current:
        lines.append(current)

    total_height_needed = len(lines) * line_gap
    fits = total_height_needed <= rect.height + 0.01

    y = rect.y0 + fontsize  # baseline of first line
    for i, line_words in enumerate(lines):
        is_last = (i == len(lines) - 1)
        words_width = sum(_word_font(w).text_length(w, fontsize=fontsize) for w in line_words)
        n_gaps = len(line_words) - 1

        if align == "justify" and not is_last and n_gaps > 0:
            gap_w = (box_width - words_width) / n_gaps
        else:
            gap_w = space_w

        line_natural_width = words_width + gap_w * n_gaps
        if align == "center" and (align != "justify" or is_last):
            x = rect.x0 + (box_width - line_natural_width) / 2
        elif align == "right" and (align != "justify" or is_last):
            x = rect.x0 + (box_width - line_natural_width)
        else:
            x = rect.x0

        for j, word in enumerate(line_words):
            page.insert_text((x, y), word, fontsize=fontsize, fontname=_word_fontname(word), color=color)
            w = _word_font(word).text_length(word, fontsize=fontsize)
            x += w + gap_w

        y += line_gap

    return fits


def _insert_right_aligned(page, text, bbox, fontsize, color=BRAND_PINK, fontname="helv", fontfile=None, fontbuffer=None):
    if not text:
        return
    rect = fitz.Rect(bbox)
    font_obj = fitz.Font(fontname=None if (fontfile or fontbuffer) else fontname,
                          fontfile=fontfile, fontbuffer=fontbuffer)
    tw = font_obj.text_length(str(text), fontsize=fontsize)
    x = rect.x1 - tw
    y = rect.y1 - (rect.height - fontsize) / 2 - 1
    page.insert_text((x, y), str(text), fontsize=fontsize, fontname=fontname, color=color)


def fill_front_side(row, template_path=TEMPLATE_PATH, config_path=CONFIG_PATH, mapping=None,
                     product_font_bytes=None, price_font_bytes=None, product_bold_font_bytes=None):
    """Returns a fitz.Document with the front side filled in.
    Pass `mapping` directly (a dict, same shape as the JSON) to skip
    reading from disk — used by the in-app live preview/adjustor.
    `product_font_bytes` / `price_font_bytes`: raw TTF/OTF bytes to use
    instead of the default fonts (for live-testing a real Arial /
    Myriad Pro Semibold font before committing it to fonts/)."""
    if mapping is None:
        mapping = load_mapping(config_path)
    doc = fitz.open(template_path)
    page = doc[0]

    pn_cfg = mapping.get("product_name")
    if pn_cfg and row.get("product_name"):
        rect = fitz.Rect(pn_cfg["bbox"])
        color = COLOR_MAP.get(pn_cfg.get("color", "black"), BLACK)
        fontname = "helv"
        if product_font_bytes:
            page.insert_font(fontbuffer=product_font_bytes, fontname="product_font")
            fontname = "product_font"
        elif os.path.exists(UNICODE_FONT_PATH):
            page.insert_font(fontfile=UNICODE_FONT_PATH, fontname="unicode_font")
            fontname = "unicode_font"

        align_str = pn_cfg.get("align", "left")
        text = str(row["product_name"])
        fontfile_arg = None if (product_font_bytes or fontname != "unicode_font") else UNICODE_FONT_PATH
        fontbuffer_arg = product_font_bytes

        bold_fontname = "product_font_bold"
        bold_fontfile_arg = None if product_bold_font_bytes else (BOLD_FONT_PATH if os.path.exists(BOLD_FONT_PATH) else None)
        bold_fontbuffer_arg = product_bold_font_bytes
        if not (bold_fontfile_arg or bold_fontbuffer_arg):
            bold_fontname = None  # no bold font available — country codes render regular

        if pn_cfg.get("auto_fit"):
            # Auto-shrink fontsize (from max down to min) until the text
            # just fits the box — matches Illustrator's "fill the box"
            # look regardless of how long this particular row's text is.
            max_fs = float(pn_cfg.get("max_fontsize", pn_cfg["fontsize"]))
            min_fs = float(pn_cfg.get("min_fontsize", 3.0))
            step = float(pn_cfg.get("fit_step", 0.1))
            chosen_fs = min_fs
            fs = max_fs
            while fs >= min_fs:
                scratch = fitz.open()
                scratch_page = scratch.new_page(width=rect.width, height=rect.height)
                fits = _wrap_and_justify_textbox(
                    scratch_page, fitz.Rect(0, 0, rect.width, rect.height), text, fs,
                    fontname, color, align=align_str, fontfile=fontfile_arg, fontbuffer=fontbuffer_arg,
                    bold_fontname=bold_fontname, bold_fontfile=bold_fontfile_arg, bold_fontbuffer=bold_fontbuffer_arg,
                )
                scratch.close()
                if fits:
                    chosen_fs = fs
                    break
                fs = round(fs - step, 2)
            _wrap_and_justify_textbox(page, rect, text, chosen_fs, fontname, color, align=align_str,
                                       fontfile=fontfile_arg, fontbuffer=fontbuffer_arg,
                                       bold_fontname=bold_fontname, bold_fontfile=bold_fontfile_arg,
                                       bold_fontbuffer=bold_fontbuffer_arg)
        else:
            fits = _wrap_and_justify_textbox(page, rect, text, pn_cfg["fontsize"], fontname, color,
                                              align=align_str, fontfile=fontfile_arg, fontbuffer=fontbuffer_arg,
                                              bold_fontname=bold_fontname, bold_fontfile=bold_fontfile_arg,
                                              bold_fontbuffer=bold_fontbuffer_arg)
            if not fits:
                # Text did NOT fit in the box at this fontsize (would overflow
                # vertically). Surface this instead of silently overflowing.

                import warnings
                warnings.warn(
                    f"product_name textbox overflow at fontsize={pn_cfg['fontsize']}. "
                    f"Box too small or fontsize too big — shrink fontsize or enlarge bbox. "
                    f"(Tip: set \"auto_fit\": true in the config to fix this automatically.)"
                )

    price_fontname = "helv"
    price_fontfile = None
    price_fontbuffer = None
    if price_font_bytes:
        page.insert_font(fontbuffer=price_font_bytes, fontname="price_font")
        price_fontname = "price_font"
        price_fontbuffer = price_font_bytes
    elif os.path.exists(MYRIADPRO_FONT_PATH):
        page.insert_font(fontfile=MYRIADPRO_FONT_PATH, fontname="price_font")
        price_fontname = "price_font"
        price_fontfile = MYRIADPRO_FONT_PATH

    for col, field_cfg in mapping.get("prices", {}).items():
        value = row.get(col, "")
        if value:
            price_color = COLOR_MAP.get(field_cfg.get("color", "black"), BLACK)
            _insert_right_aligned(page, value, field_cfg["bbox"], field_cfg["fontsize"], color=price_color,
                                   fontname=price_fontname, fontfile=price_fontfile, fontbuffer=price_fontbuffer)

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
