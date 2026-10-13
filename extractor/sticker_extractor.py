# ================================================================
#  extractor/sticker_extractor.py
#  Sticker data — PAGE 4 and onwards: TC number, barcode, product name,
#  kg, season, qty. PAGE 1: Pictogram, Promotional.
#  (Ported from old extractor.py / PEPCO_Data_Extractor/sticker_extractor.py
#  — logic unchanged, only re-packaged into this module.)
# ================================================================
import re

from extractor.constants import PICTOGRAM_MAPPING, PROMOTIONAL_MAPPING


def extract_all_tc_numbers_from_page4_plus(pages_text):
    """ALL TC numbers from PAGE 4 onwards. Max 7 unique, in order-of-appearance."""
    tc_list = []
    if len(pages_text) >= 4:
        for i in range(3, len(pages_text)):
            for pattern in (r"TC\s*-\s*(T\d+)", r"TC\s*[:.]?\s*(T\d+)"):
                for m in re.findall(pattern, pages_text[i], re.IGNORECASE):
                    if m not in tc_list:
                        tc_list.append(m)
    return tc_list[:7]


def extract_all_barcodes_from_page4_plus(pages_text):
    """ALL 13-digit barcodes from PAGE 4 onwards. Max 7 unique, in order-of-appearance."""
    barcode_list = []
    if len(pages_text) >= 4:
        for i in range(3, len(pages_text)):
            barcode_list.extend(re.findall(r"\b\d{13}\b", pages_text[i]))
    seen, out = set(), []
    for b in barcode_list:
        if b not in seen:
            seen.add(b)
            out.append(b)
    return out[:7]


def extract_product_name_from_page4_plus(pages_text):
    if len(pages_text) >= 4:
        for i in range(3, len(pages_text)):
            text = pages_text[i]
            m = re.search(r"ITEM\s*\d+\s*\n\s*(.+)", text, re.IGNORECASE)
            if not m:
                m = re.search(r"Product\s*name\s*[:.]?\s*(.+)", text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
    return ""


def extract_inner_kg_from_page4_plus(pages_text):
    if len(pages_text) >= 4:
        for i in range(3, len(pages_text)):
            text = pages_text[i]
            m = re.search(r"MAX\.?\s*(\d+)\s*kg", text, re.IGNORECASE)
            if not m:
                m = re.search(r"(\d+)\s*kg", text, re.IGNORECASE)
            if m:
                return f"MAX. {m.group(1)} kg"
    return ""


def extract_season_from_page4_plus(pages_text):
    if len(pages_text) >= 4:
        for i in range(3, len(pages_text)):
            m = re.search(r"\b(AW|SS|FW|SW)\d{2}\b", pages_text[i], re.IGNORECASE)
            if m:
                return m.group(0).upper()
    return ""


def extract_inner_qty_from_page4_plus(pages_text):
    if len(pages_text) >= 4:
        for i in range(3, len(pages_text)):
            m = re.search(r"(\d+)\s*Pcs", pages_text[i], re.IGNORECASE)
            if m:
                return f"{m.group(1)} Pcs"
    return ""


def extract_outer_qty_from_page4_plus(pages_text):
    if len(pages_text) >= 4:
        patterns = [
            r"(\d+)\s*Inner\s*OUTER", r"(\d+)\s*OUTER", r"OUTER\s*[:.]?\s*(\d+)",
            r"(\d+)\s*X\s*INNER\s*OUTER", r"OUTER\s*QTY\s*[:.]?\s*(\d+)",
        ]
        for i in range(3, len(pages_text)):
            text = pages_text[i]
            for p in patterns:
                m = re.search(p, text, re.IGNORECASE)
                if m:
                    return f"{m.group(1)} Inner"
    return ""


def extract_sticker_data(pages_text):
    """Ekbar-e shob sticker data extract kore 1-ta dict e.
    'pictogram'..'outer_qty' -> single value (shob row-e same).
    'tc_numbers' / 'barcodes' -> list, position onujayi row-e boshe
    (sticker_values_for_row diye)."""
    page1 = pages_text[0] if pages_text else ""

    all_tc_numbers = extract_all_tc_numbers_from_page4_plus(pages_text)
    all_barcodes = extract_all_barcodes_from_page4_plus(pages_text)
    product_name = extract_product_name_from_page4_plus(pages_text)
    inner_kg = extract_inner_kg_from_page4_plus(pages_text)
    season_st = extract_season_from_page4_plus(pages_text)
    inner_qty = extract_inner_qty_from_page4_plus(pages_text)
    outer_qty = extract_outer_qty_from_page4_plus(pages_text)

    pictogram = ""
    m = re.search(r"Pictogram\s*no.*?(PIC\d{5})", page1, re.IGNORECASE | re.DOTALL)
    if m:
        pictogram = PICTOGRAM_MAPPING.get(m.group(1).upper(), "")

    promotional = ""
    m = re.search(r"Promotional\s*product.*?(NON\s+PROMO|PROMO|KVI|HS)\b", page1, re.IGNORECASE | re.DOTALL)
    if m:
        value = re.sub(r"\s+", " ", m.group(1).strip()).upper()
        if value != "NON PROMO":
            promotional = PROMOTIONAL_MAPPING.get(value, "")

    return {
        "pictogram": pictogram,
        "promotional": promotional,
        "product_name": product_name,
        "inner_kg": inner_kg,
        "season_st": season_st,
        "inner_qty": inner_qty,
        "outer_qty": outer_qty,
        "tc_numbers": all_tc_numbers,
        "barcodes": all_barcodes,
    }


def sticker_values_for_row(sticker: dict, idx: int) -> dict:
    """idx-tomo row-er jonno sticker column gulo. TC_Number_st / Barcode_st
    — row onujayi (1 row = 1 sticker entry): 1st row-er TC/Barcode = 1st,
    2nd row-er = 2nd ... config/inner/outer_field_mapping.json ei nam-i pore."""
    tcs = sticker["tc_numbers"]
    bcs = sticker["barcodes"]
    return {
        "Pictogram": sticker["pictogram"],
        "Promotional": sticker["promotional"],
        "Product_name": sticker["product_name"],
        "Inner_kg": sticker["inner_kg"],
        "Season_st": sticker["season_st"],
        "Inner_qty": sticker["inner_qty"],
        "Outer_qty": sticker["outer_qty"],
        "TC_Number_st": tcs[idx] if idx < len(tcs) else "",
        "Barcode_st": bcs[idx] if idx < len(bcs) else "",
    }
