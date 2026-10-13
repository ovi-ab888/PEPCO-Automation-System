"""
extractor/  (package — replaces the old single-file extractor.py)

Public API — UNCHANGED from the old extractor.py, so app.py's
    extractor.extract_rows_from_pdfs(pdf_files)
    extractor.build_filename(row, extension=..., template_name=...)
calls keep working with no edits there.

Difference from before: extract_rows_from_pdfs() now returns MULTIPLE rows
per PDF (one per SKU/Size/Barcode combination) instead of a single row with
TC_Number_st1..7 / Barcode_st1..7 numbered columns.
"""
import pandas as pd

from extractor.pdf_extractor import extract_rows_from_pdf, extract_order_id_only

__all__ = ["extract_rows_from_pdfs", "build_filename"]


def build_filename(row: dict, extension: str = "pdf", template_name: str = "Sticker") -> str:
    """
    Filename pattern:
    PEPCO_{SEASON}_{SKUs}_{TEMPLATE_NAME}_{SUPPLIER_CODE}_00_{STYLE}.{extension}

    row must still have "_temp_sku_for_filename" (call this before dropping
    that column from the dataframe).
    """
    season_val = str(row.get("Season", "UNKNOWN")).upper() or "UNKNOWN"
    sku = row.get("_temp_sku_for_filename", "UNKNOWN")
    supplier_code = row.get("Supplier_product_code", "UNKNOWN")
    style_val = row.get("Style", "UNKNOWN")
    return f"PEPCO_{season_val}_{sku}_{template_name} {supplier_code}_00_{style_val}.{extension}"


def extract_rows_from_pdfs(pdf_files) -> pd.DataFrame:
    """
    pdf_files: list of uploaded PDFs. First is the primary sticker/order PDF
    (produces multiple rows — one per SKU/Size/Barcode); any additional PDFs
    only contribute their Order ID (concatenated onto every row's Order_ID),
    same behaviour as before for multi-order jobs.
    """
    if not pdf_files:
        return pd.DataFrame()

    primary, others = pdf_files[0], pdf_files[1:]
    extra_ids = []
    for f in others:
        oid = extract_order_id_only(f)
        if oid:
            extra_ids.append(oid)

    rows = extract_rows_from_pdf(primary, extra_order_ids="+".join(extra_ids))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)
