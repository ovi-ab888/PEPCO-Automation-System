"""
extractor.py
Extracts label data directly from a PEPCO tech-pack/order PDF — ported from
PEPCO_Label_Automation_V3 (app.py). Returns a pandas DataFrame with exactly
the columns our label engine (inner/outer/pad) already expects, so its
output can be fed straight into labels.pad_label.generate_batch() etc.
without any renaming.
"""
import re
from datetime import datetime

import fitz  # PyMuPDF
import pandas as pd

PICTOGRAM_MAPPING = {
    "PIC00033": "A", "PIC00019": "8", "PIC00020": "9", "PIC00034": "B", "PIC00009": "R",
    "PIC00182": "3", "PIC00181": "5", "PIC00028": "S", "PIC00032": "C", "PIC00010": "Q",
    "PIC00178": "1", "PIC00014": "L", "PIC00011": "N", "PIC00183": "4", "PIC00186": "7",
    "PIC00184": "2", "PIC00012": "M", "PIC00031": "E", "PIC00029": "F", "PIC00027": "G",
    "PIC00185": "6", "PIC00013": "O", "PIC00180": "0", "PIC00030": "D",
}
PROMOTIONAL_MAPPING = {"PROMO": "P", "KVI": "K", "HS": "H"}


def _extract_all_tc_numbers_from_page4_plus(pages_text):
    tc_list = []
    if len(pages_text) >= 4:
        for i in range(3, len(pages_text)):
            for pattern in [r"TC\s*-\s*(T\d+)", r"TC\s*[:.]?\s*(T\d+)"]:
                for m in re.findall(pattern, pages_text[i], re.IGNORECASE):
                    if m not in tc_list:
                        tc_list.append(m)
    return tc_list[:7]


def _extract_all_barcodes_from_page4_plus(pages_text):
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


def _extract_product_name_from_page4_plus(pages_text):
    if len(pages_text) >= 4:
        for i in range(3, len(pages_text)):
            text = pages_text[i]
            m = re.search(r"ITEM\s*\d+\s*\n\s*(.+)", text, re.IGNORECASE)
            if not m:
                m = re.search(r"Product\s*name\s*[:.]?\s*(.+)", text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
    return ""


def _extract_inner_kg_from_page4_plus(pages_text):
    if len(pages_text) >= 4:
        for i in range(3, len(pages_text)):
            text = pages_text[i]
            m = re.search(r"MAX\.?\s*(\d+)\s*kg", text, re.IGNORECASE)
            if not m:
                m = re.search(r"(\d+)\s*kg", text, re.IGNORECASE)
            if m:
                return f"MAX. {m.group(1)} kg"
    return ""


def _extract_season_from_page4_plus(pages_text):
    if len(pages_text) >= 4:
        for i in range(3, len(pages_text)):
            m = re.search(r"\b(AW|SS|FW|SW)\d{2}\b", pages_text[i], re.IGNORECASE)
            if m:
                return m.group(0).upper()
    return ""


def _extract_inner_qty_from_page4_plus(pages_text):
    if len(pages_text) >= 4:
        for i in range(3, len(pages_text)):
            m = re.search(r"(\d+)\s*Pcs", pages_text[i], re.IGNORECASE)
            if m:
                return f"{m.group(1)} Pcs"
    return ""


def _extract_outer_qty_from_page4_plus(pages_text):
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


def _clean_item_name_english(name: str) -> str:
    if not isinstance(name, str):
        return ""
    text = re.sub(r"^\d+\.\s*", "", name.strip()).strip()
    return text.upper()


def _extract_colour(pages_text):
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
    return ""  # left blank — user fills it in during the correction step


def extract_order_id_only(file) -> str | None:
    """Extract just the Order ID from an extra PDF (used to concatenate multiple orders)."""
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


def extract_row_from_pdf(file, extra_order_ids: str = "") -> dict | None:
    """
    file: an uploaded PDF (file-like, .read() available).
    Returns one row dict with exactly the columns the label engine expects,
    or None if extraction fails outright (e.g. not a valid PDF).
    """
    raw = file.read()
    if not raw:
        return None
    doc = fitz.open(stream=raw, filetype="pdf")
    if len(doc) < 1:
        return None

    pages_text = [doc[i].get_text() for i in range(len(doc))]
    full_text = "\n".join(pages_text)
    page1 = pages_text[0]

    all_tc_numbers = _extract_all_tc_numbers_from_page4_plus(pages_text)
    all_barcodes = _extract_all_barcodes_from_page4_plus(pages_text)
    product_name = _extract_product_name_from_page4_plus(pages_text)
    inner_kg = _extract_inner_kg_from_page4_plus(pages_text)
    season_st = _extract_season_from_page4_plus(pages_text)
    inner_qty = _extract_inner_qty_from_page4_plus(pages_text)
    outer_qty = _extract_outer_qty_from_page4_plus(pages_text)

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

    item_name_en = ""
    m_item = re.search(r"Item\s*name\s*English\s*[:\.]{1,}\s*(.+)", full_text, re.IGNORECASE)
    if not m_item:
        m_item = re.search(r"Item\s*name\s*[:\.]{1,}\s*(.+?)\n", full_text, re.IGNORECASE)
    if m_item:
        item_name_en = m_item.group(1).strip()

    style_code = re.search(r"\b\d{6}\b", page1)
    order_id = re.search(r"Order\s*-\s*ID\s*\.{2,}\s*(.+)", page1)
    item_class = re.search(r"Item classification\s*\.{2,}\s*(.+)", page1)
    supplier_code = re.search(r"Supplier product code\s*\.{2,}\s*(.+)", page1)
    supplier_name = re.search(r"Supplier name\s*\.{2,}\s*(.+)", page1)
    season = re.search(r"Season\s*\.{2,}\s*(\w+)?\s*(\d{2})", page1)

    colour = _extract_colour(pages_text)

    # 8-digit SKUs across all pages, deduped, joined with "_" — used only for
    # the download filename (matches the original V3 CSV-download naming).
    skus = []
    for txt in pages_text:
        skus.extend(re.findall(r"\b\d{8}\b", txt))
    seen_sku, unique_skus = set(), []
    for s in skus:
        if s not in seen_sku:
            seen_sku.add(s)
            unique_skus.append(s)
    sku_for_filename = "_".join(unique_skus) if unique_skus else "UNKNOWN"

    row = {
        "Order_ID": (order_id.group(1).strip() if order_id else "") + (f"+{extra_order_ids}" if extra_order_ids else ""),
        "Style": style_code.group() if style_code else "",
        "Colour": colour.title() if colour else "",
        "Supplier_product_code": supplier_code.group(1).strip() if supplier_code else "",
        "Item_classification": item_class.group(1).strip() if item_class else "",
        "Supplier_name": supplier_name.group(1).strip() if supplier_name else "",
        "today_date": datetime.today().strftime("%d-%m-%Y"),
        "Item_name_English": _clean_item_name_english(item_name_en),
        "Season": f"{season.group(1)}{season.group(2)}" if season else "",
        "Pictogram": pictogram,
        "Promotional": promotional,
        "Product_name": product_name,
        "Inner_kg": inner_kg,
        "Season_st": season_st,
        "Inner_qty": inner_qty,
        "Outer_qty": outer_qty,
        "_temp_sku_for_filename": sku_for_filename,
    }
    for i in range(7):
        row[f"TC_Number_st{i+1}"] = all_tc_numbers[i] if i < len(all_tc_numbers) else ""
    for i in range(7):
        row[f"Barcode_st{i+1}"] = all_barcodes[i] if i < len(all_barcodes) else ""

    return row


def build_filename(row: dict, extension: str = "pdf", template_name: str = "Sticker") -> str:
    """
    Filename pattern:
    PEPCO_{SEASON}_{SKUs}_{TEMPLATE_NAME}_{SUPPLIER_CODE}_00_{STYLE}.{extension}

    template_name = the actual template PDF's filename (without extension)
    from the templates/ folder that this label type uses — e.g. "pad" for
    templates/pad.pdf. Falls back to "Sticker" if not given, for backward
    compatibility with any old caller that doesn't pass it.

    row must still have "_temp_sku_for_filename" (i.e. call this before
    dropping that column from the dataframe).
    """
    season_val = str(row.get("Season", "UNKNOWN")).upper() or "UNKNOWN"
    sku = row.get("_temp_sku_for_filename", "UNKNOWN")
    supplier_code = row.get("Supplier_product_code", "UNKNOWN")
    style_val = row.get("Style", "UNKNOWN")
    return f"PEPCO_{season_val}_{sku}_{template_name}_{supplier_code}_00_{style_val}.{extension}"


def extract_rows_from_pdfs(pdf_files) -> pd.DataFrame:
    """
    pdf_files: list of uploaded PDFs. First is the primary sticker/order PDF;
    any additional ones only contribute their Order ID (concatenated onto
    the primary row's Order_ID) — mirrors the original V3 app's behaviour
    for multi-order jobs. The returned DataFrame includes the hidden
    "_temp_sku_for_filename" column — drop it before showing/editing, use it
    via build_filename() before dropping.
    """
    if not pdf_files:
        return pd.DataFrame()

    primary, others = pdf_files[0], pdf_files[1:]
    extra_ids = []
    for f in others:
        oid = extract_order_id_only(f)
        if oid:
            extra_ids.append(oid)

    row = extract_row_from_pdf(primary, extra_order_ids="+".join(extra_ids))
    if row is None:
        return pd.DataFrame()
    return pd.DataFrame([row])
