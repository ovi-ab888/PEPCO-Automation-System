"""
labels/size_tag.py
Size Tag stickers — templates live in a folder tree on disk:

    templates/Sizetag/<Type>/<Department>/<Customer>/<size file>.pdf

e.g. templates/Sizetag/Regular/PB & PG/All/Size Tag.pdf

The available Type / Department / Customer / size-file options are
discovered at RUNTIME by scanning this folder tree — adding a new
combination is just dropping a new folder/PDF into templates/Sizetag/ on
GitHub, no code changes needed here or in app.py.

All Sizetag PDFs share the same header layout (Order ID, Item, Style Code,
Color, Designer, etc. — same positions as pad_header_mapping.json) plus
Item_name_English repeated across the 6 size panels, so they all use the
one config/size_tag_mapping.json.
"""
import os
import json
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from engine.label_engine import fill_single_label, fill_placeholders_by_search

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
SIZETAG_ROOT = os.path.join(BASE_DIR, "templates", "Sizetag")
CONFIG_PATH = os.path.join(BASE_DIR, "config", "size_tag_mapping.json")

# used only as a filename-logic fallback if nothing has been selected yet
TEMPLATE_PATH = None

# The item name on each panel is a literal "{Item_name_English}" placeholder
# in the template artwork — found and replaced wherever it appears, so it
# works no matter how many panels a given template has or where they sit.
ITEM_NAME_FONT = "poppins_semibold"
ITEM_NAME_FONT_SIZE = 12


def _list_subfolders(path: str) -> list:
    if not os.path.isdir(path):
        return []
    return sorted(d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d)))


def _list_pdfs(path: str) -> list:
    if not os.path.isdir(path):
        return []
    return sorted(f for f in os.listdir(path) if f.lower().endswith(".pdf"))


def list_types() -> list:
    """Level 1: e.g. ['Regular', 'With OEKO-TEX']"""
    return _list_subfolders(SIZETAG_ROOT)


def list_departments(type_name: str) -> list:
    """Level 2: e.g. ['PB & PG', 'OB & OG']"""
    return _list_subfolders(os.path.join(SIZETAG_ROOT, type_name))


def list_customers(type_name: str, department: str) -> list:
    """Level 3: e.g. ['All', 'K. C. PRINT LTD.']"""
    return _list_subfolders(os.path.join(SIZETAG_ROOT, type_name, department))


def list_sizes(type_name: str, department: str, customer: str) -> list:
    """Level 4: the actual PDF filenames, e.g. ['Size Tag.pdf']"""
    return _list_pdfs(os.path.join(SIZETAG_ROOT, type_name, department, customer))


def get_template_path(type_name: str, department: str, customer: str, size_file: str) -> str:
    return os.path.join(SIZETAG_ROOT, type_name, department, customer, size_file)


def load_field_config() -> list:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def _fill_one(template_path: str, row: dict) -> bytes:
    # 1. header fields at fixed coordinates (shared across every Sizetag template)
    header_config = load_field_config()
    header_filled = fill_single_label(template_path, row, header_config)

    # 2. item name — found by searching for the literal "{Item_name_English}"
    #    placeholder text, wherever and however many times it appears
    final_bytes = fill_placeholders_by_search(
        header_filled, row,
        font=ITEM_NAME_FONT, font_size=ITEM_NAME_FONT_SIZE,
        token_columns=["Item_name_English"],
    )
    return final_bytes


def generate_single(row: dict, template_path: str) -> bytes:
    return _fill_one(template_path, row)


def generate_batch(rows: list, template_path: str) -> bytes:
    """rows = list of Excel row dicts. template_path = the specific PDF
    chosen via the Type/Department/Customer/Size cascade (use
    get_template_path() to build it)."""
    import fitz
    merged = fitz.open()
    for row in rows:
        single_bytes = _fill_one(template_path, row)
        single_doc = fitz.open("pdf", single_bytes)
        merged.insert_pdf(single_doc)
        single_doc.close()
    out = merged.tobytes()
    merged.close()
    return out
