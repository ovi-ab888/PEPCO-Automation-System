# ================================================================
#  extractor/pdf_extractor.py
#  PEPCO PDF theke directly shob data extract kora — MULTI-ROW version:
#  ekta PDF => multiple rows (1 SKU/Size/Barcode combination = 1 row),
#  age-r "1 PDF = 1 row + TC_Number_st1..7 numbered columns" model theke
#  notun "1 PDF = N rows, TC_Number_st1/Barcode_st1 shudhu ei row-tar
#  nijer value" model-e switch kora hoyeche.
#
#  Column-naming existing label engine (engine/label_engine.py,
#  labels/*.py, config/*.json) er shathe compatible rakha hoyeche —
#  Phase-2 update na kore-o eta drop-in hisebe kaj korbe emon design.
# ================================================================
import re
from datetime import datetime

import fitz  # PyMuPDF

from extractor.auto_fields import (
    make_today_date,
    make_colour_sku,
    make_style_merch_season,
    make_batch,
    clean_item_name_english,
)
from extractor.sticker_extractor import extract_sticker_data, sticker_values_for_row
from extractor.cm_size import get_cm_size


# ================================================================
#  SIZES  (full comma-joined string — "3/4, 4/5, 5/6")
# ================================================================
def extract_sizes_from_pdf(pages_text):
    size_pattern = re.compile(
        r"^(?:\d+(?:[/-]\d+)?|[A-Za-z]{1,4}(?:/[A-Za-z]{1,4})?)$",
        re.IGNORECASE,
    )
    for text in pages_text:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            if line.lower() == "sizes":
                sizes = []
                for next_line in lines[idx + 1:]:
                    upper = next_line.upper()
                    if upper == "TOTAL":
                        break
                    if upper == "COLOUR":
                        continue
                    for cand in re.split(r"\s*,\s*", next_line):
                        cand = cand.strip()
                        if cand and size_pattern.fullmatch(cand) and cand.upper() not in ("COLOUR", "TOTAL"):
                            sizes.append(cand)
                if sizes:
                    return ", ".join(sizes)
    return ""


# ================================================================
#  PL SALES PRICE  (new enrichment — CSV-export feature-er PLN auto-fill)
# ================================================================
def extract_pl_sales_price_from_pdf(pages_text):
    for text in pages_text:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            if line == "PL" or line.startswith("PL "):
                prices = re.findall(r"\b\d+(?:[.,]\d{2})\b", line)
                if prices:
                    return prices[0].replace(",", ".")
                for next_line in lines[idx + 1:idx + 5]:
                    prices = re.findall(r"\b\d+(?:[.,]\d{2})\b", next_line)
                    if prices:
                        return prices[0].replace(",", ".")
    return ""


# ================================================================
# COLLECTION  ([TYPE -] NAME - SEASON - CODE)
#   "COL - DOUBLE TAKE - SS27 - 131" -> DOUBLE TAKE
#   "EV - REAL MADRID - SS27 - 142"  -> REAL MADRID
#   "REG - BASIC - SS27 - 141"       -> BASIC
#   "DESSERT TRIP - SS27 - 112"      -> DESSERT TRIP  (TYPE nai)
# ================================================================
_SEASON_RE = re.compile(r"[A-Za-z]{2}\d{2}")   # SS27, AW26

def extract_collection_value(raw_text):
    if not raw_text:
        return "UNKNOWN"

    # " - " (space-hyphen-space) diye split, jate MINI-ME er moto name na bhange
    parts = [p.strip() for p in re.split(r"\s+-\s+", raw_text.strip()) if p.strip()]
    if not parts:
        return "UNKNOWN"

    # Season er age-r ongsho = [TYPE] + NAME
    season_idx = next((i for i, p in enumerate(parts) if _SEASON_RE.fullmatch(p)), None)
    if season_idx is not None:
        name_parts = parts[:season_idx]
    else:
        name_parts = list(parts)                       # season na thakle shesh-er CODE bad
        while name_parts and name_parts[-1].isdigit():
            name_parts.pop()

    # 2+ part thakle prothom part = TYPE (COL / EV / REG ...), bad
    if len(name_parts) >= 2:
        name_parts = name_parts[1:]

    return " - ".join(name_parts) if name_parts else "UNKNOWN"


# ================================================================
#  COLOUR
# ================================================================
def extract_colour(pages_text):
    for txt in pages_text:
        m = re.search(r"Colour.*?\n.*?\n\s*([A-Za-z ]+)\s+[0-9]{2}-[0-9]{4}", txt, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip().upper()
    for txt in pages_text:
        m2 = re.search(r"Purchase price.*?\n\s*([A-Za-z ]+)\s+[0-9]{2}-[0-9]{4}", txt, re.IGNORECASE | re.DOTALL)
        if m2:
            return m2.group(1).strip().upper()
    for txt in pages_text:
        if "colour" in txt.lower():
            for line in txt.splitlines():
                if re.search(r"[A-Za-z ]+\s+[0-9]{2}-[0-9]{4}", line):
                    name = line.split()[0:-1]
                    if name:
                        return " ".join(name).upper()
    return ""  # blank -> user fills in during the app.py correction step


# ================================================================
#  ORDER ID ONLY  (extra PDF upload-er jonno)
# ================================================================
def extract_order_id_only(file):
    try:
        file.seek(0)
    except Exception:
        pass
    try:
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            page1_text = doc[0].get_text() if len(doc) > 0 else ""
    except Exception:
        return None
    finally:
        try:
            file.seek(0)
        except Exception:
            pass
    m = re.search(r"Order\s*-\s*ID\s*\.{2,}\s*([A-Z0-9_+-]+)", page1_text, re.IGNORECASE)
    return m.group(1).strip() if m else None


# ================================================================
#  MAIN MULTI-ROW EXTRACTION
# ================================================================
def extract_rows_from_pdf(file, extra_order_ids: str = "") -> list:
    """
    file: an uploaded PDF (file-like, .read() available).
    Returns a LIST of row dicts — one per SKU/Size/Barcode combination
    found in the PDF — or [] if extraction fails outright.
    """
    raw = file.read()
    if not raw:
        return []
    doc = fitz.open(stream=raw, filetype="pdf")
    if len(doc) < 1:
        return []

    pages_text = [doc[i].get_text() for i in range(len(doc))]
    full_text = "\n".join(pages_text)
    page1 = pages_text[0]

    # ---------------- Sticker data (page 4+) ----------------
    sticker = extract_sticker_data(pages_text)

    # ---------------- Item name (English) ----------------
    item_name_en = ""
    m_item = re.search(r"Item\s*name\s*English\s*[:\.]{1,}\s*(.+)", full_text, re.IGNORECASE)
    if not m_item:
        m_item = re.search(r"Item\s*name\s*[:\.]{1,}\s*(.+?)\n", full_text, re.IGNORECASE)
    if m_item:
        item_name_en = m_item.group(1).strip()

    # ---------------- Sizes ----------------
    sizes = extract_sizes_from_pdf(pages_text)
    pl_price_detected = extract_pl_sales_price_from_pdf(pages_text)

    # ---------------- Identifiers ----------------
    style_code = re.search(r"\b\d{6}\b", page1)
    order_id = re.search(r"Order\s*-\s*ID\s*\.{2,}\s*(.+)", page1)
    item_class = re.search(r"Item classification\s*\.{2,}\s*(.+)", page1)
    supplier_code = re.search(r"Supplier product code\s*\.{2,}\s*(.+)", page1)
    supplier_name = re.search(r"Supplier name\s*\.{2,}\s*(.+)", page1)
    season = re.search(r"Season\s*\.{2,}\s*(\w+)?\s*(\d{2})", page1)
    merch_code = re.search(r"Merch\s*code\s*\.{2,}\s*([\w/]+)", page1)

    style_suffix = ""
    if merch_code and season:
        style_suffix = f"{merch_code.group(1).strip()}{season.group(2)}"
    elif merch_code:
        style_suffix = merch_code.group(1).strip()

    collection_match = re.search(r"Collection\s*\.{2,}\s*(.+)", page1)
    collection_value = extract_collection_value(collection_match.group(1)) if collection_match else "UNKNOWN"

    date_match = re.search(r"Handover\s*date\s*\.{2,}\s*(\d{2}/\d{2}/\d{4})", page1)
    batch_text = make_batch(date_match.group(1) if date_match else None)

    colour = extract_colour(pages_text)
    season_value = f"{season.group(1)}{season.group(2)}" if season else ""

    # ---------------- SKU + main barcode (all pages) ----------------
    skus, barcodes, excluded = [], [], set()
    for txt in pages_text:
        skus.extend(re.findall(r"\b\d{8}\b", txt))
        barcodes.extend(re.findall(r"\b\d{13}\b", txt))
        excluded.update(re.findall(r"barcode:\s*(\d{13})", txt))

    def _dedupe(seq):
        seen, out = set(), []
        for x in seq:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    skus = _dedupe(skus)
    valid_barcodes = [b for b in _dedupe(barcodes) if b not in excluded]

    # Filename uses ALL skus found in the PDF, joined — unchanged from the
    # old single-row extractor.py (build_filename reads this, same on every row).
    sku_for_filename = "_".join(skus) if skus else "UNKNOWN"

    order_id_value = (order_id.group(1).strip() if order_id else "") + (f"+{extra_order_ids}" if extra_order_ids else "")
    style_value = style_code.group() if style_code else ""
    item_class_value = item_class.group(1).strip() if item_class else ""
    supplier_code_value = supplier_code.group(1).strip() if supplier_code else ""
    supplier_name_value = supplier_name.group(1).strip() if supplier_name else ""
    item_name_english_value = clean_item_name_english(item_name_en)

    # ---------------- Build one row per Size (paired positionally with
    # the page4+ sticker TC/Barcode entries — same alignment the old
    # numbered-column system already relied on) ----------------
    sizes_list = [s.strip() for s in sizes.split(",")] if sizes else [""]

    results = []
    for i, size_val in enumerate(sizes_list):
        sku_this_row = skus[i] if i < len(skus) else ""
        barcode_this_row = valid_barcodes[i] if i < len(valid_barcodes) else ""

        row = {
            "Order_ID": order_id_value,
            "Style": style_value,
            "Colour": colour.title() if colour else "",
            "Supplier_product_code": supplier_code_value,
            "Item_classification": item_class_value,
            "Supplier_name": supplier_name_value,
            "today_date": make_today_date(),
            "Item_name_English": item_name_english_value,
            "Item_name_EN": item_name_en,  # NEW — raw (un-cleaned), CSV-export feature-er jonno
            "Season": season_value,
            "Sizes": size_val,         # ei row-er nijer size (row onujayi: XS / S / M ...)
            "_temp_sku_for_filename": sku_for_filename,
            "_pl_price_detected": pl_price_detected,  # NEW — hidden, CSV-export PLN auto-fill
            # ---- new enrichment fields (not read by any current template) ----
            "Collection": collection_value,
            "Colour_SKU": make_colour_sku(colour, sku_this_row),
            "Style_Merch_Season": make_style_merch_season(style_value or None, style_suffix),
            "Batch": batch_text,
            "SKU": sku_this_row,
            "barcode": barcode_this_row,
            "cm_size": get_cm_size(size_val),
            **sticker_values_for_row(sticker, i),  # Pictogram, Promotional, Product_name,
                                                    # Inner_kg, Season_st, Inner_qty, Outer_qty,
                                                    # TC_Number_st, Barcode_st
        }
        results.append(row)

    return results
