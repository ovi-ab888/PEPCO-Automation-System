"""
labels/2_pieces_set.py
2-Pieces-Set label generation logic.
Uses the same header field mapping as pad_label.py (pad_header_mapping.json)
but applies it to the 2-Pieces-Set.pdf template.
"""
import os
import json
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from engine.label_engine import fill_single_label, generate_multipage_pdf

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "two_pieces_set.pdf")  # <-- এক্সটেনশন যোগ করুন
CONFIG_PATH = os.path.join(BASE_DIR, "config", "pad_header_mapping.json")


def load_field_config():
    """Load the header field configuration from pad_header_mapping.json."""
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def generate_single(row: dict) -> bytes:
    """
    Generate a single 2-Pieces-Set label from one Excel row.
    
    Args:
        row: Dictionary containing the data for one label.
    
    Returns:
        bytes: The generated PDF as bytes.
    """
    field_config = load_field_config()
    return fill_single_label(TEMPLATE_PATH, row, field_config)


def generate_batch(rows: list) -> bytes:
    """
    Generate multiple 2-Pieces-Set labels from a list of Excel rows.
    
    Args:
        rows: List of dictionaries, each representing one label's data.
    
    Returns:
        bytes: A merged multi-page PDF containing all generated labels.
    """
    field_config = load_field_config()
    return generate_multipage_pdf(TEMPLATE_PATH, rows, field_config)
