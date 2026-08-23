"""
labels/kvi_size_stickers.py
KVI numeric size-ladder stickers (part of Benefite Tag and Sticker) — fixed size-strip artwork (Kids / Older Top / Older Top
Bottom), only the same Montrims header (Order ID, Item, Style Code, Color,
Designer, etc.) gets filled in — reuses config/pad_header_mapping.json,
same as pad_label, inner_label, outer_label.

Three template variants, selected by name:
    "Kids"              -> KIDS_KVI_Size_Sticker.pdf
    "Older Top"         -> Older_KVI_Size_Sticker_Top.pdf
    "Older Top Bottom"  -> Older_KVI_Size_Sticker_Top_Bottom.pdf
"""
import os
import json
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import fitz
from engine.label_engine import fill_single_label, generate_multipage_pdf

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
CONFIG_PATH = os.path.join(BASE_DIR, "config", "pad_header_mapping.json")

TEMPLATES = {
    "Kids": os.path.join(BASE_DIR, "templates", "KIDS_KVI_Size_Sticker.pdf"),
    "Older Top": os.path.join(BASE_DIR, "templates", "Older_KVI_Size_Sticker_Top.pdf"),
    "Older Top Bottom": os.path.join(BASE_DIR, "templates", "Older_KVI_Size_Sticker_Top_Bottom.pdf"),
}

# default used when a caller doesn't specify (e.g. generic app.py wiring
# that just calls generate_batch(rows) with no size-type argument yet)
DEFAULT_TEMPLATE_KEY = "Kids"
TEMPLATE_PATH = TEMPLATES[DEFAULT_TEMPLATE_KEY]  # used for filename derivation


def load_field_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def generate_single(row: dict, size_type: str = DEFAULT_TEMPLATE_KEY) -> bytes:
    """size_type must be one of TEMPLATES.keys()."""
    template_path = TEMPLATES.get(size_type, TEMPLATES[DEFAULT_TEMPLATE_KEY])
    field_config = load_field_config()
    return fill_single_label(template_path, row, field_config)


def generate_batch(rows: list, size_type: str = DEFAULT_TEMPLATE_KEY) -> bytes:
    """rows = list of Excel row dicts. Returns one merged multi-page PDF."""
    template_path = TEMPLATES.get(size_type, TEMPLATES[DEFAULT_TEMPLATE_KEY])
    field_config = load_field_config()
    return generate_multipage_pdf(template_path, rows, field_config)
