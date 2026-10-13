# ================================================================
#  extractor/auto_fields.py
#  PDF-e nai, code nije generate kore emon field gulo:
#     today_date, Colour_SKU, Style_Merch_Season, Batch, Item_name_English
#  (Ported from PEPCO_Data_Extractor/auto_fields.py; Dept/get_dept_value
#  skipped — CSV-export-only, needed na ei label engine-e.)
# ================================================================
import re
from datetime import datetime, timedelta


def make_today_date():
    """Ajker date, DD-MM-YYYY."""
    return datetime.today().strftime("%d-%m-%Y")


def make_colour_sku(colour, sku):
    """'WHITE • SKU 12345678' — notun enrichment field, kono existing
    label template ei column reference kore na (safe to add)."""
    return f"{colour} • SKU {sku}" if sku else ""


def make_style_merch_season(style_code, style_suffix=""):
    """'STYLE 123456 • <suffix> • Batch No./' — notun enrichment field."""
    if not style_code:
        return "STYLE UNKNOWN"
    return f"STYLE {style_code} • {style_suffix} • Batch No./"


def make_batch(handover_date):
    """Handover date - 20 din -> 'виготовлення: MMYYYY'.
    handover_date: 'dd/mm/YYYY' string, na thakle None."""
    batch = "UNKNOWN"
    if handover_date:
        try:
            batch_date = datetime.strptime(handover_date, "%d/%m/%Y")
            batch = (batch_date - timedelta(days=20)).strftime("%m%Y")
        except Exception:
            pass
    return f"виготовлення: {batch}"


def clean_item_name_english(name: str) -> str:
    """Item name theke leading '4. ' / '12. ' numbering bad diye CAPITAL
    kore return kore — old extractor.py-r logic hubuhu (Item_name_English
    field-ta size_tag.py-r PDF template-e '{Item_name_English}' hishebe
    literal search hoy, tai eta age-r moto-i thakche)."""
    if not isinstance(name, str):
        return ""
    text = re.sub(r"^\d+\.\s*", "", name.strip()).strip()
    return text.upper()
