"""
labels/benefite.py
"Benefite Tag and Sticker" — templates live under templates/Benefite/ in
TWO possible shapes:

  1. Flat file:   templates/Benefite/<Sticker Type>.pdf
     e.g. templates/Benefite/Two_Pieces_Set.pdf
     -> a single-variant type, used directly, no dropdown needed.

  2. Nested folder: templates/Benefite/<Sticker Type>/<variant file>.pdf
     e.g. templates/Benefite/KVI Size Sticker/Kids.pdf
     -> multiple variants; the UI shows a picker (or auto-picks, see below).

Adding a new sticker type, or a new variant of an existing one, is just
dropping a new file/folder into templates/Benefite/ on GitHub — no code
changes needed here or in app.py.

NOTE: Inner & Outer Sticker is intentionally NOT part of this folder — it
stays its own separate, standalone item (labels/pad_label.py), not scanned
here.

--- Auto-select-by-Sizes folders (KVI Size Sticker, Utag, ...) ---
Some folders hold one PDF per size-range family, with the range(s) encoded
right in the filename, using -, : or / as the separator, e.g.:
    templates/Benefite/KVI Size Sticker/KVI_Size_Sticker 3:4, 4:5, 5:6.pdf
    templates/Benefite/Utag/Utag  0:3, 3:6, 6:9, 9:12, 12:18.pdf
For these, no manual variant dropdown is shown — generate_batch_auto_size()
picks the right file PER ROW:
  - If the row's own Sizes are themselves ranges (e.g. "3/4, 4/5"), they
    are matched EXACTLY against a filename's encoded ranges — this avoids
    false ties between overlapping wide-range files (e.g. a file covering
    "0:0, 0:3, 3:6...12:18" numerically overlaps "3:4, 4:5...8:9" too, so
    exact range matching is needed, not just "does this number fall
    inside this range").
  - Otherwise (plain sizes like "9, 10, S, M"), falls back to checking
    whether each size number falls inside one of the filename's ranges,
    or a literal substring match for non-range filenames.
This means a single checkbox in the UI can correctly cover rows with
different Sizes each, without the user choosing anything extra.

Folders using this behaviour are listed in AUTO_SIZE_TYPES below — add a
type name there when its variant filenames encode sizes this way.

All Benefite templates share the same header layout as Inner_Outer_Sticker/
Size Tag, so they use config/pad_header_mapping.json too.
"""
import os
import json
import re
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import fitz
from engine.label_engine import fill_single_label, generate_multipage_pdf

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
BENEFITE_ROOT = os.path.join(BASE_DIR, "templates", "Benefite")
CONFIG_PATH = os.path.join(BASE_DIR, "config", "pad_header_mapping.json")

# used only as a filename-logic fallback if nothing has been selected yet
TEMPLATE_PATH = None

# sticker types whose variant files should be auto-matched against each
# row's Sizes value, rather than picked manually via dropdown
AUTO_SIZE_TYPES = {"KVI Size Sticker", "Utag"}


def _list_subfolders(path: str) -> list:
    if not os.path.isdir(path):
        return []
    return sorted(d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d)))


def _list_pdfs(path: str) -> list:
    if not os.path.isdir(path):
        return []
    return sorted(f for f in os.listdir(path) if f.lower().endswith(".pdf"))


def list_sticker_types() -> list:
    """Every available sticker type — both nested folders AND flat
    top-level PDFs (templates/Benefite/<Type>.pdf, using the filename
    without extension as the type name)."""
    types = set(_list_subfolders(BENEFITE_ROOT))
    for f in _list_pdfs(BENEFITE_ROOT):
        types.add(os.path.splitext(f)[0])
    return sorted(types)


def list_variants(sticker_type: str) -> list:
    """PDF filenames for this type — from its folder if nested, or just
    its single flat file if not."""
    folder = os.path.join(BENEFITE_ROOT, sticker_type)
    if os.path.isdir(folder):
        return _list_pdfs(folder)
    flat_path = os.path.join(BENEFITE_ROOT, sticker_type + ".pdf")
    if os.path.exists(flat_path):
        return [sticker_type + ".pdf"]
    return []


def get_template_path(sticker_type: str, variant_file: str) -> str:
    folder = os.path.join(BENEFITE_ROOT, sticker_type)
    if os.path.isdir(folder):
        return os.path.join(folder, variant_file)
    return os.path.join(BENEFITE_ROOT, variant_file)


def is_auto_size_type(sticker_type: str) -> bool:
    return sticker_type in AUTO_SIZE_TYPES


def _extract_ranges(text: str):
    """Finds ALL numeric ranges in text, any separator (-, :, /).
    e.g. '0:3, 3:6, 6:9' -> [(0,3), (3,6), (6,9)]"""
    return [(int(a), int(b)) for a, b in re.findall(r"(\d+)\s*[:/-]\s*(\d+)", text)]


def _leading_number(token: str):
    m = re.search(r"\d+", token)
    return int(m.group()) if m else None


def pick_variant_for_row(sticker_type: str, row: dict) -> str:
    variants = list_variants(sticker_type)
    if not variants:
        return None

    sizes_str = str(row.get("Sizes", "")).strip()
    if not sizes_str:
        return variants[0]

    size_tokens = [s.strip() for s in sizes_str.split(",") if s.strip()]

    row_ranges = []
    for tok in size_tokens:
        m = re.match(r"^(\d+)\s*[:/-]\s*(\d+)$", tok)
        if m:
            row_ranges.append((int(m.group(1)), int(m.group(2))))

    best_variant, best_key = None, None
    for variant in variants:
        file_ranges = _extract_ranges(variant)
        if row_ranges and file_ranges:
            matches = sum(1 for r in row_ranges if r in file_ranges)
            # prefer more matches, then FEWER extra ranges in the file
            # (an exact-size file beats a wider superset file that also
            # happens to contain all the same ranges)
            key = (matches, -abs(len(file_ranges) - len(row_ranges)))
        elif file_ranges:
            size_numbers = [n for n in (_leading_number(t) for t in size_tokens) if n is not None]
            matches = sum(1 for n in size_numbers if any(lo <= n <= hi for lo, hi in file_ranges))
            key = (matches, -abs(len(file_ranges) - len(size_numbers)))
        else:
            matches = sum(1 for tok in size_tokens if tok.lower() in variant.lower())
            key = (matches, 0)

        if best_key is None or key > best_key:
            best_key, best_variant = key, variant

    return best_variant if best_key and best_key[0] > 0 else variants[0]

def load_field_config() -> list:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def generate_single(row: dict, template_path: str) -> bytes:
    field_config = load_field_config()
    return fill_single_label(template_path, row, field_config)


def generate_batch(rows: list, template_path: str) -> bytes:
    """rows = list of Excel row dicts. template_path = the specific PDF
    chosen via the sticker-type/variant selection (use get_template_path())."""
    field_config = load_field_config()
    return generate_multipage_pdf(template_path, rows, field_config)


def generate_batch_auto_size(rows: list, sticker_type: str) -> bytes:
    """For AUTO_SIZE_TYPES: picks the right variant file PER ROW (matching
    that row's Sizes against the available filenames) and merges the
    result into one PDF — no manual variant selection needed."""
    field_config = load_field_config()
    merged = fitz.open()
    for row in rows:
        variant = pick_variant_for_row(sticker_type, row)
        if not variant:
            continue
        template_path = get_template_path(sticker_type, variant)
        single_bytes = fill_single_label(template_path, row, field_config)
        single_doc = fitz.open("pdf", single_bytes)
        merged.insert_pdf(single_doc)
        single_doc.close()
    out = merged.tobytes()
    merged.close()
    return out
