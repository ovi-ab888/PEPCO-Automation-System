"""
labels/two_packs.py
Two Packs Sticker label generation logic.
Uses the same header field mapping as pad_label.py (pad_header_mapping.json)
but applies it to the Two_Packs_Sticker.pdf template.
"""
import os
import json
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from engine.label_engine import fill_single_label, generate_multipage_pdf

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "Two_Packs_Sticker.pdf")
CONFIG_PATH = os.path.join(BASE_DIR, "config", "pad_header_mapping.json")


def load_field_config():
    """Load the header field configuration from pad_header_mapping.json."""
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def generate_single(row: dict) -> bytes:
    """
    Generate a single Two Packs Sticker label from one Excel row.
    
    Args:
        row: Dictionary containing the data for one label.
    
    Returns:
        bytes: The generated PDF as bytes.
    """
    field_config = load_field_config()
    return fill_single_label(TEMPLATE_PATH, row, field_config)


def generate_batch(rows: list) -> bytes:
    """
    Generate multiple Two Packs Sticker labels from a list of Excel rows.
    
    Args:
        rows: List of dictionaries, each representing one label's data.
    
    Returns:
        bytes: A merged multi-page PDF containing all generated labels.
    """
    field_config = load_field_config()
    return generate_multipage_pdf(TEMPLATE_PATH, rows, field_config)
