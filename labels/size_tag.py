"""
labels/size_tag.py
Size Tag stickers (Regular / With OEKO-TEX variants) — 6-panel size ladder
with the item's English name printed on each panel. Header (Order ID, Item,
Style Code, Color, Designer, etc.) uses the same layout as
pad_label/inner_label/outer_label, via config/size_tag_mapping.json (a copy
of pad_header_mapping.json's shape, plus Item_name_English x6).

Two template variants, selected by name:
    "Regular"   -> Size_Tag_Regular.pdf    (70mm x 46mm)
    "OEKO-TEX"  -> Size_Tag_OEKO_TEX.pdf   (86mm x 46mm, has the OEKO-TEX
                   certification badge on each panel)

NOTE: the "PRODUCT NAME" / item-name text in the source templates uses a
Poppins-SemiBold font we don't have a .ttf for yet — falls back to
Helvetica-Bold (hebo) for now. Drop Poppins-SemiBold.ttf into /fonts and
update the "font" key in config/size_tag_mapping.json to switch to it later.
"""
import os
import json
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from engine.label_engine import fill_single_label, generate_multipage_pdf

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
CONFIG_PATH = os.path.join(BASE_DIR, "config", "size_tag_mapping.json")

TEMPLATES = {
    "Regular": os.path.join(BASE_DIR, "templates", "Size_Tag_Regular.pdf"),
    "OEKO-TEX": os.path.join(BASE_DIR, "templates", "Size_Tag_OEKO_TEX.pdf"),
}

DEFAULT_TEMPLATE_KEY = "Regular"
TEMPLATE_PATH = TEMPLATES[DEFAULT_TEMPLATE_KEY]  # used for filename derivation


def load_field_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def generate_single(row: dict, variant: str = DEFAULT_TEMPLATE_KEY) -> bytes:
    """variant must be one of TEMPLATES.keys()."""
    template_path = TEMPLATES.get(variant, TEMPLATES[DEFAULT_TEMPLATE_KEY])
    field_config = load_field_config()
    return fill_single_label(template_path, row, field_config)


def generate_batch(rows: list, variant: str = DEFAULT_TEMPLATE_KEY) -> bytes:
    """rows = list of Excel row dicts. Returns one merged multi-page PDF."""
    template_path = TEMPLATES.get(variant, TEMPLATES[DEFAULT_TEMPLATE_KEY])
    field_config = load_field_config()
    return generate_multipage_pdf(template_path, rows, field_config)
