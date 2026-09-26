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
right in the filename, using -, :, / or _ as the separator, e.g.:
    templates/Benefite/KVI Size Sticker/KVI_Size_Sticker 3:4, 4:5, 5:6.pdf
    templates/Benefite/Utag/Utag 3_4, 4_5, 5_6, 6_7, 7_8, 8_9.pdf
For these, no manual variant dropdown is shown — generate_batch_auto_size()
picks the right file PER ROW, via pick_variant_for_row(), in this order:

  1. EXPLICIT OVERRIDE — config/benefite_size_overrides.json can map a
     sticker type's exact Sizes string straight to a filename. This is the
     most reliable option for a known/problematic case (see that file's
     own comment) and always wins over the heuristics below.
  2. EXACT-SET match — the row's size tokens (as ranges, or as plain
     tokens/numbers) are compared as a SET against each candidate file's
     own extracted tokens. A file whose tokens are EXACTLY the same set as
     the row's wins outright — this beats any "coverage" style match
     (e.g. a wide range file that happens to numerically contain the same
     numbers) so there's no ambiguous tie between an exact match and a
     superset match.
  3. Heuristic scoring fallback — for partial/inexact matches: exact range
     tuples in common, or how many size numbers fall inside a file's
     range(s), or how many size tokens are literally present as tokens in
     the filename (not substring — see _extract_size_tokens).

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
SIZE_OVERRIDES_PATH = os.path.join(BASE_DIR, "config", "benefite_size_overrides.json")

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


# Separators seen across real filenames so far: colon, slash, hyphen,
# underscore (e.g. "Utag 3_4, 4_5...pdf" uses "_" instead of "/" because
# "/" can't appear in a filename on some systems).
_RANGE_SEP = r"[:/_-]"


def _extract_ranges(text: str):
    """Finds ALL numeric ranges in text, any separator (-, :, /, _).
    e.g. '0:3, 3:6, 6:9' -> [(0,3), (3,6), (6,9)]"""
    return [(int(a), int(b)) for a, b in re.findall(rf"(\d+)\s*{_RANGE_SEP}\s*(\d+)", text)]


def _leading_number(token: str):
    m = re.search(r"\d+", token)
    return int(m.group()) if m else None


_SIZE_TOKEN_RE = re.compile(r"\b(XXXXL|XXXL|XXL|XL|XXS|XS|S|M|L|\d+)\b", re.IGNORECASE)


def _extract_size_tokens(text: str):
    """Extracts EXACT clothing-size tokens (S, M, L, XL, XXL, XXXL, or
    plain numbers) from text, word-boundary anchored — NOT substring
    matching. This avoids 'L' or 'XL' being falsely counted as present
    just because they're literally substrings of 'XL'/'XXL'/'XXXL'."""
    return [m.group(1).upper() for m in _SIZE_TOKEN_RE.finditer(text)]


def _load_size_overrides() -> dict:
    try:
        with open(SIZE_OVERRIDES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _normalize_sizes_key(sizes_str: str) -> str:
    """Normalizes a Sizes string for override lookup: strip, collapse
    whitespace around commas, so '9,10, 11 ,12' and '9, 10, 11, 12' both
    hit the same override entry."""
    tokens = [t.strip() for t in sizes_str.split(",") if t.strip()]
    return ", ".join(tokens)


def pick_variant_for_row(sticker_type: str, row: dict) -> str:
    variants = list_variants(sticker_type)
    if not variants:
        return None

    sizes_str = str(row.get("Sizes", "")).strip()
    if not sizes_str:
        return variants[0]

    # ---- 1) Explicit override (config/benefite_size_overrides.json) ----
    overrides = _load_size_overrides()
    type_overrides = overrides.get(sticker_type, {})
    override_file = type_overrides.get(_normalize_sizes_key(sizes_str))
    if override_file and override_file in variants:
        return override_file

    size_tokens = [s.strip() for s in sizes_str.split(",") if s.strip()]

    row_ranges = []
    for tok in size_tokens:
        m = re.match(rf"^(\d+)\s*{_RANGE_SEP}\s*(\d+)$", tok)
        if m:
            row_ranges.append((int(m.group(1)), int(m.group(2))))

    # ---- 2) Exact-SET match (beats any partial/coverage match) ----
    if row_ranges:
        row_range_set = set(row_ranges)
        for variant in variants:
            if set(_extract_ranges(variant)) == row_range_set:
                return variant
    else:
        row_token_set = set(t.upper() for t in size_tokens)
        for variant in variants:
            if set(_extract_size_tokens(variant)) == row_token_set:
                return variant

    # ---- 3) Heuristic scoring fallback ----
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
            # Letter sizes (XS/S/M/L/XL/XXL/XXXL, ...) or plain numbers —
            # match on EXACT tokens extracted from the filename, never raw
            # substring (substring would wrongly count "L"/"XL" as present
            # in "XXL"/"XXXL" too, since they literally contain those
            # letters in sequence).
            file_tokens = set(_extract_size_tokens(variant))
            row_tokens_upper = [t.upper() for t in size_tokens]
            matches = sum(1 for tok in row_tokens_upper if tok in file_tokens)
            key = (matches, -abs(len(file_tokens) - len(size_tokens)))

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
