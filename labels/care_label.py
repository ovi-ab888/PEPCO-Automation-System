"""
care_label.py
==============
PEPCO Care Label — Pad generator.

One Pad page =
    * N x "Front Part 1"  (one per size: cm_size, |PEPCO|, EAN, SKU, washing
      code pictogram, then the START of the long Composition_Care text)
    * 5 panels that carry the REST of the Composition_Care text, in this
      reading order:
          Front Part 1 (lower part) -> Back Part 1 -> Front Part 2
          -> Back Part 2 -> Front Part 3 -> Back Part 3
      (Composition_Care is one long text with blank lines used as vertical
      gaps; it is wrapped with real Arial metrics and poured line by line
      into the panels, exactly like the sample file.)

"Produced by ... + importer address" block:
      Kept together in ONE panel (never split). It goes to Front Part 3 when
      the Care Instructions text before it is short; if that text already
      reaches Front Part 3 it goes to Back Part 3, then Front Part 4, and so
      on. Front/Back Part 4 (and 5 on the wide Pad 2) are not in the Pad
      templates - they are drawn (with a pink caption) only when needed.

"Made in Bangladesh ..." paragraph:
      Anchored to the BOTTOM of the panel just before the Produced-by panel
      (bottom of Back Part 2 when Produced by is in Front Part 3, bottom of
      Front Part 3 when it is in Back Part 3, ...), like the sample file.
      The "Skupljanje: po dužini ..." line sits 4 lines (skupljanje_gap_lines
      = 3 blank lines) above the first Made-in line.

Pad template choice (per group of sizes):
      <= 6 sizes -> Care_Label_Pad.pdf     (6 Front Part 1 slots)
      7-8 sizes  -> Care_Label_Pad 2.pdf   (8 Front Part 1 slots)
      > 8 sizes  -> split into several Pad pages (8 per page)
Unused Front Part 1 slots are simply left empty.

Data columns used (from the editable table / CSV):
    cm_size, barcode, SKU, washing_code, Composition_Care      <- label content
    Order_ID, Style, Supplier_product_code, Colour, today_date,
    Designer, Item_classification, Supplier_name               <- Pad header

Repo structure needed:
    labels/care_label.py                       (this file)
    config/care_label_mapping.json
    fonts/ArialRegular.ttf  fonts/ArialBold.ttf
    fonts/PEPCO_Ovi.ttf     fonts/Tahoma.ttf
    templates/Care label/   Front Side_part1.pdf, Front Side.pdf, Back Side.pdf,
                            Care_Label_Pad.pdf, Care_Label_Pad 2.pdf
    (template file names are matched ignoring case, spaces and underscores)
"""

import json
import os
import re

import fitz  # PyMuPDF

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
CONFIG_PATH = os.path.join(BASE_DIR, "config", "care_label_mapping.json")
TEMPLATES_ROOT = os.path.join(BASE_DIR, "templates")
FONTS_DIR = os.path.join(BASE_DIR, "fonts")

BLACK = (0, 0, 0, 1)  # CMYK K100, print-safe black (same as the other labels)

REQUIRED_COLUMNS = ["cm_size", "barcode", "SKU", "washing_code", "Composition_Care"]


class CareLabelOverflow(ValueError):
    """Composition_Care is longer than the 6 text areas can hold."""


# --------------------------------------------------------------------------
# helpers: config, file lookup, fonts
# --------------------------------------------------------------------------
def load_mapping(config_path=CONFIG_PATH):
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _norm(name: str) -> str:
    """'Front Side_part1.pdf' -> 'frontsidepart1' (ignore case/space/_/-/extension)."""
    base = os.path.splitext(name)[0]
    return "".join(ch for ch in base.lower() if ch.isalnum())


def _find_templates_dir() -> str:
    """templates/Care label  (also matches 'Care Label', 'Care_Label', ...)."""
    for entry in os.listdir(TEMPLATES_ROOT):
        full = os.path.join(TEMPLATES_ROOT, entry)
        if os.path.isdir(full) and _norm(entry) == "carelabel":
            return full
    raise FileNotFoundError(f"templates/Care label folder not found under {TEMPLATES_ROOT}")


def _find_template(key: str) -> str:
    folder = _find_templates_dir()
    for entry in os.listdir(folder):
        if _norm(entry) == key and entry.lower().endswith(".pdf"):
            return os.path.join(folder, entry)
    raise FileNotFoundError(f"Care Label template '{key}' not found in {folder}")


def _find_font(*candidates) -> str:
    """Case-insensitive lookup of a font file in fonts/."""
    wanted = {_norm(c) for c in candidates}
    for entry in os.listdir(FONTS_DIR):
        if entry.lower().endswith((".ttf", ".otf")) and _norm(entry) in wanted:
            return os.path.join(FONTS_DIR, entry)
    raise FileNotFoundError(f"Font {candidates} not found in {FONTS_DIR}")


class _Fonts:
    """Loads the 3 Care Label fonts once: measuring objects + file paths."""

    def __init__(self):
        self.files = {
            "arial": _find_font("ArialRegular", "arial"),
            "arialb": _find_font("ArialBold", "arialbd"),
            "ovi": _find_font("PEPCO_Ovi"),
        }
        self.objs = {k: fitz.Font(fontfile=v) for k, v in self.files.items()}

    def register(self, page):
        for key, path in self.files.items():
            page.insert_font(fontname=key, fontfile=path)

    def width(self, key, text, size):
        return self.objs[key].text_length(text, fontsize=size)


def _s(value) -> str:
    """Cell -> clean string (NaN / None -> '')."""
    if value is None or (isinstance(value, float) and value != value):
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d-%m-%Y")
    s = str(value)
    return "" if s.strip().lower() == "nan" else s


# --------------------------------------------------------------------------
# text flow
# --------------------------------------------------------------------------
def wrap_composition(text: str, fonts: _Fonts, size: float, width: float,
                     wide_prefixes=(), wide_width: float = None) -> list:
    """
    Wrap Composition_Care into lines. Every '\\n' starts a new line; an empty
    line stays an EMPTY string (= one blank line of vertical gap).
    Paragraphs starting with one of `wide_prefixes` (e.g. "Skupljanje" - the
    shrinkage line, which the sample prints on ONE line) may use the wider
    `wide_width` if that keeps them on a single line.
    """
    lines = []
    text = _s(text).replace("\r\n", "\n").replace("\r", "\n")
    for para in text.split("\n"):
        para = " ".join(para.split())
        if not para:
            lines.append("")
            continue
        if (wide_width and para.startswith(tuple(wide_prefixes))
                and fonts.width("arial", para, size) <= wide_width):
            lines.append(para)
            continue
        cur = ""
        for word in para.split():
            trial = f"{cur} {word}" if cur else word
            if fonts.width("arial", trial, size) <= width:
                cur = trial
                continue
            if cur:
                lines.append(cur)
                cur = ""
            # a single word wider than the box -> hard-break by characters
            while fonts.width("arial", word, size) > width and len(word) > 1:
                cut = len(word) - 1
                while cut > 1 and fonts.width("arial", word[:cut], size) > width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            cur = word
        if cur:
            lines.append(cur)
    return lines


def _capacity(first_baseline: float, last_baseline: float, pitch: float) -> int:
    return int((last_baseline - first_baseline) / pitch + 1e-6) + 1


def split_care_and_block(text: str, marker: str):
    """
    Split Composition_Care into (care_instructions_text, block_text).
    The block starts at the first line that begins with `marker`
    ("Produced by...") and runs to the end (importer address block).
    No marker -> (text, "").
    """
    text = _s(text).replace("\r\n", "\n").replace("\r", "\n")
    if not marker:
        return text, ""
    m = re.search(r"(?m)^[ \t]*" + re.escape(marker), text)
    if not m:
        return text, ""
    return text[:m.start()], text[m.start():]


def split_made_in(care_text: str, marker: str):
    """
    Split the text that comes BEFORE the 'Produced by' block into
    (care_instructions_text, made_in_text). The Made-in paragraph starts at the
    first line beginning with `marker` ("Made in Bangladesh...") and runs to
    the end of `care_text`. No marker -> (care_text, "").
    """
    if not marker:
        return care_text, ""
    m = re.search(r"(?m)^[ \t]*" + re.escape(marker), care_text)
    if not m:
        return care_text, ""
    return care_text[:m.start()], care_text[m.start():]


def split_line_out(text: str, marker: str):
    """
    Cut the line that starts with `marker` ("Skupljanje: ...") out of `text`.
    Returns (text_without_that_line, that_line). No marker/match -> (text, "").
    """
    if not marker:
        return text, ""
    m = re.search(r"(?m)^[ \t]*" + re.escape(marker) + r"[^\n]*\n?", text)
    if not m:
        return text, ""
    return text[:m.start()] + text[m.end():], m.group(0)


def _trim_blank(lines: list) -> list:
    i, j = 0, len(lines)
    while i < j and lines[i] == "":
        i += 1
    while j > i and lines[j - 1] == "":
        j -= 1
    return lines[i:j]


def flow_into_panels(care_lines: list, block_lines: list, mapping: dict, panels: list,
                     made_lines: list = None) -> dict:
    """
    1) Pour the Care Instructions lines into Front Part 1 (lower part) + the
       panels, in reading order (blank lines at the TOP of a panel are dropped).
    2) Put the 'Produced by + address' block, UNSPLIT, into ONE panel: Front
       Part 3 at the earliest; if the care text already reaches Front 3 it goes
       to the next empty panel (Back 3, then Front 4, ...).
    3) If `made_lines` (the "Made in Bangladesh ..." paragraph) is given, it is
       anchored to the BOTTOM of the panel just before the Produced-by panel.
       It needs `made_gap_min_lines` blank line(s) after the care text; if it
       does not fit there, the Made-in / Produced-by pair moves one panel on.
    Returns {"front1": [...], "back1": [...], ...}. Raises CareLabelOverflow.
    """
    comp = mapping["composition"]
    pitch, last = comp["line_pitch"], comp["last_baseline"]
    order = [("front1", comp["front1_first_baseline"])] + \
            [(p["name"], p["first_baseline"]) for p in panels]
    names = [n for n, _ in order]
    # a panel may carry its own "last_baseline" (Back panels: keep 5 mm above the pink dash line)
    lasts = [last] + [p.get("last_baseline", last) for p in panels]
    caps = [_capacity(first, lasts[i], pitch) for i, (_, first) in enumerate(order)]

    out, i, last_used, used_in_last = {}, 0, -1, 0
    for idx, (name, first) in enumerate(order):
        cap = caps[idx]
        while i < len(care_lines) and care_lines[i] == "":   # trim blank lines at panel top
            i += 1
        chunk = care_lines[i:i + cap]
        out[name] = chunk
        i += len(chunk)
        if any(chunk):
            last_used = idx
            used_in_last = max(n for n, ln in enumerate(chunk) if ln) + 1   # ignore trailing blanks
    rest = [ln for ln in care_lines[i:] if ln != ""]
    if rest:
        raise CareLabelOverflow(
            f"Care Instructions text is too long for this Pad: {len(rest)}+ line(s) "
            f"do not fit after {names[-1].replace('front', 'Front Part ').replace('back', 'Back Part ')}. "
            f"Shorten the composition text."
        )

    block = _trim_blank(block_lines)
    made = _trim_blank(made_lines or [])
    if block:
        min_name = comp.get("block_min_panel", "front3")
        min_idx = names.index(min_name) if min_name in names else 0
        bidx = max(min_idx, last_used + 1)
        gap = comp.get("made_gap_min_lines", 1)
        if made:
            # panel before the block must hold [care text] + gap + [Made-in at bottom]
            while bidx - 1 == last_used and used_in_last + gap + len(made) > caps[bidx - 1]:
                bidx += 1
            if len(made) > caps[bidx - 1]:
                raise CareLabelOverflow(f"The 'Made in' paragraph ({len(made)} lines) does not fit in one panel.")
        if bidx >= len(order):
            raise CareLabelOverflow(
                "Care Instructions text is so long that the 'Produced by' block has no panel "
                "left on this Pad. Shorten the composition text."
            )
        bname, bfirst = order[bidx]
        if len(block) > caps[bidx]:
            raise CareLabelOverflow(
                f"The 'Produced by' block ({len(block)} lines) does not fit in one panel."
            )
        out[bname] = block
        if made:
            pidx = bidx - 1
            pname = names[pidx]
            kept = out[pname][:used_in_last] if pidx == last_used else []   # care text exactly as flowed
            pad = caps[pidx] - len(made) - len(kept)
            out[pname] = kept + [""] * pad + made
    elif made:
        raise CareLabelOverflow("Internal: made-in lines given without a Produced-by block.")
    return out


def _draw_lines(page, fonts, rect, first_baseline, lines, mapping):
    comp = mapping["composition"]
    size, pitch = comp["font_size"], comp["line_pitch"]
    cx = (rect.x0 + rect.x1) / 2
    for n, ln in enumerate(lines):
        if not ln:
            continue
        w = fonts.width("arial", ln, size)
        page.insert_text((cx - w / 2, rect.y0 + first_baseline + n * pitch), ln,
                         fontsize=size, fontname="arial", color=BLACK)


# --------------------------------------------------------------------------
# drawing the pieces
# --------------------------------------------------------------------------
def _draw_front1_fields(page, fonts, rect, row, mapping):
    ff = mapping["front_fields"]
    cx = (rect.x0 + rect.x1) / 2
    a, big, ovi = ff["arial_size"], ff["cm_size_font"], ff["ovi_size"]

    def centered(text, font, size, baseline):
        if not text:
            return
        w = fonts.width(font, text, size)
        page.insert_text((cx - w / 2, rect.y0 + baseline), text, fontsize=size,
                         fontname=font, color=BLACK)

    centered(_s(row.get("cm_size")).strip(), "arialb", big, ff["cm_size_baseline"])
    centered(ff.get("pepco_text", "|PEPCO|"), "arial", a, ff["pepco_baseline"])
    barcode = _s(row.get("barcode")).strip()
    centered(f"EAN: {barcode}" if barcode else "", "arial", a, ff["ean_baseline"])
    sku = _s(row.get("SKU")).strip()
    centered(f"SKU {sku}" if sku else "", "arialb", a, ff["sku_baseline"])
    centered(_s(row.get("washing_code")).strip(), "ovi", ovi, ff["washing_baseline"])


def _fill_pad_header(page, rows, mapping):
    tahoma = None
    try:
        tahoma = _find_font("Tahoma")
        page.insert_font(fontname="tahoma", fontfile=tahoma)
    except FileNotFoundError:
        pass
    fontname = "tahoma" if tahoma else "helv"

    for field in mapping.get("header", []):
        vals = [_s(r.get(field["name"])).strip() for r in rows]
        vals = [v for v in vals if v]
        if not vals:
            continue
        sep = field.get("join_unique")
        value = sep.join(dict.fromkeys(vals)) if sep else vals[0]
        page.insert_text((field["x"], field["y"]), value, fontsize=field["font_size"],
                         fontname=fontname, color=BLACK)


def _show(page, rect, template_path):
    src = fitz.open(template_path)
    page.show_pdf_page(fitz.Rect(rect), src, 0)
    src.close()


# --------------------------------------------------------------------------
# grouping + generation
# --------------------------------------------------------------------------
def group_rows_for_pads(rows: list, mapping: dict = None) -> list:
    """
    Consecutive rows with the same Composition_Care share a Pad (a different
    composition always starts a new Pad), at most 8 sizes (the biggest Pad
    template) per Pad page.
    """
    if mapping is None:
        mapping = load_mapping()
    biggest = max(p["max_units"] for p in mapping["pads"])
    groups, cur, cur_key = [], [], None
    for row in rows:
        key = _s(row.get("Composition_Care")).strip()
        if cur and (key != cur_key or len(cur) >= biggest):
            groups.append(cur)
            cur = []
        cur.append(row)
        cur_key = key
    if cur:
        groups.append(cur)
    return groups


def pick_pad_for_group(n_units: int, mapping: dict) -> dict:
    """Smallest Pad template that has enough Front Part 1 slots."""
    for pad in sorted(mapping["pads"], key=lambda p: p["max_units"]):
        if n_units <= pad["max_units"]:
            return pad
    raise ValueError(f"No Care Label Pad template holds {n_units} sizes")


def _draw_panel_label(page, fonts, rect, text):
    """Pink 'Front Part 4' style caption above an extra panel (same spot/colour as the Pad's own captions)."""
    size = 11.5
    w = fonts.width("arial", text, size)
    page.insert_text(((rect.x0 + rect.x1) / 2 - w / 2, rect.y0 - 8.5), text, fontsize=size,
                     fontname="arial", color=(0.925, 0, 0.549))


def generate_pad_for_group(group_rows: list, mapping: dict = None, fonts: _Fonts = None) -> bytes:
    """ONE Pad page (PDF bytes) for a group of rows (one row = one size)."""
    if mapping is None:
        mapping = load_mapping()
    if not group_rows:
        raise ValueError("group_rows is empty")
    fonts = fonts or _Fonts()

    pad_cfg = pick_pad_for_group(len(group_rows), mapping)
    pad_doc = fitz.open(_find_template(pad_cfg["template"]))
    page = pad_doc[0]
    # extra panels (Front/Back Part 4, 5 ...) only if they fit inside this Pad's width
    panels = [p for p in mapping["panels"] if p["rect"][2] <= page.rect.x1 - 8]

    comp = mapping["composition"]
    care_text, block_text = split_care_and_block(group_rows[0].get("Composition_Care", ""),
                                                 comp.get("block_marker", ""))
    made_text = skup_text = ""
    if block_text.strip():       # Made-in is anchored to the panel before 'Produced by'
        care_text, made_text = split_made_in(care_text, comp.get("made_in_marker", ""))
        if made_text.strip():    # Skupljanje line rides along, a few lines above Made-in
            care_text, skup_text = split_line_out(care_text, comp.get("skupljanje_marker", ""))
    wrap = lambda t: wrap_composition(t, fonts, comp["font_size"], comp["wrap_width"],
                                      comp.get("wide_prefixes", ()), comp.get("wide_width"))
    made_lines = None
    if made_text.strip():
        made_lines = _trim_blank(wrap(made_text))
        if skup_text.strip():
            made_lines = _trim_blank(wrap(skup_text)) + [""] * comp.get("skupljanje_gap_lines", 3) + made_lines
    flow = flow_into_panels(wrap(care_text), wrap(block_text), mapping, panels,
                            made_lines)  # may raise CareLabelOverflow

    fonts.register(page)
    _fill_pad_header(page, group_rows, mapping)

    front1_tpl = _find_template(mapping["front1_template"])
    for rect_coords, row in zip(pad_cfg["front_rects"], group_rows):
        rect = fitz.Rect(rect_coords)
        _show(page, rect, front1_tpl)
        _draw_front1_fields(page, fonts, rect, row, mapping)
        _draw_lines(page, fonts, rect, comp["front1_first_baseline"], flow["front1"], mapping)
    # Front Part 1 slots with no size stay as the empty template box

    for panel in panels:
        lines = flow.get(panel["name"], [])
        if panel.get("extra") and not any(lines):
            continue                      # extra panel not needed -> leave the Pad area empty
        rect = fitz.Rect(panel["rect"])
        _show(page, rect, _find_template(panel["template"]))
        if panel.get("extra") and panel.get("label"):
            _draw_panel_label(page, fonts, rect, panel["label"])
        _draw_lines(page, fonts, rect, panel["first_baseline"], lines, mapping)

    data = pad_doc.tobytes()
    pad_doc.close()
    return data


def generate_batch(rows: list, config_path=CONFIG_PATH) -> list:
    """List of Pad PDF bytes, one per group."""
    mapping = load_mapping(config_path)
    fonts = _Fonts()
    return [generate_pad_for_group(g, mapping, fonts) for g in group_rows_for_pads(rows, mapping)]


def generate_batch_pdf(rows: list, config_path=CONFIG_PATH) -> bytes:
    """Same as generate_batch(), merged into ONE multi-page PDF."""
    out = fitz.open()
    for pad_bytes in generate_batch(rows, config_path):
        src = fitz.open("pdf", pad_bytes)
        out.insert_pdf(src)
        src.close()
    data = out.tobytes()
    out.close()
    return data


def missing_columns(rows: list) -> list:
    """Care Label columns that are absent or completely empty in the table."""
    return [c for c in REQUIRED_COLUMNS if not any(_s(r.get(c)).strip() for r in rows)]
