# ================================================================
#  enrichment/enrich.py
#  PDF theke extract howa table-e NOTUN column gulo add kore:
#     - UI input diye:  Dept/Product Type/Washing Code/PLN Price/
#                       Material Composition + Care Instructions
#     - Google Sheet theke: product_name (multi-language), currency
#                           price ladder, material/care translations
#  Result: FINAL_COLS-er shob column ekhon ei table-e thake, tai
#  Inner/Outer, Benefite, Size Tag, Hangtag, Care Label shob-i ei data pabe.
#
#  NOTE: TC_Number_st / Barcode_st / Sizes ekhon row onujayi (1 row = 1 size).
#  Product_name (purono) ar Product_name_st ekhono duitai ache.
# ================================================================
import re

import pandas as pd
import streamlit as st

from enrichment.constants import WASHING_CODES
from enrichment.data_loaders import load_product_translations
from enrichment.classification import (
    map_item_class_to_dept_label,
    modify_collection,
    map_collection_name,
)
from enrichment.translation import format_product_translations
from enrichment.price_helpers import parse_pln_price, apply_price_columns
from enrichment.composition_care import render_composition_care_section

# Final table-e ei order-e prothome thakbe (baki purono column pichone)
FINAL_COLS = [
    "Order_ID", "Style", "Colour", "Supplier_product_code",
    "Item_classification", "Supplier_name", "today_date",
    "Collection", "Colour_SKU", "Style_Merch_Season",
    "Batch", "barcode", "washing_code", "EUR", "BGN",
    "BAM", "PLN", "RON", "CZK", "UAH", "MKD", "RSD", "HUF",
    "product_name", "Dept", "Item_name_English", "Season", "Sizes",
    "cm_size", "Cotton",
    "Pictogram", "Promotional", "Product_name_st", "Inner_kg", "Season_st",
    "Inner_qty", "Outer_qty", "TC_Number_st", "Barcode_st",
    "Composition_Care",
]

# Helper column — user-er table-e dekhanor dorkar nai
_HIDDEN_COLS = ["Item_name_EN"]


def _get_dept_value(item_class):
    """Item_classification -> BABY / KIDS / TEENS / WOMEN / MEN."""
    ic = (item_class or "").lower()
    if any(x in ic for x in ["baby boys", "baby girls"]):
        return "BABY"
    if any(x in ic for x in ["younger boys", "younger girls"]):
        return "KIDS"
    if any(x in ic for x in ["older girls", "older boys"]):
        return "TEENS"
    if "ladies outerwear" in ic:
        return "WOMEN"
    if "mens outerwear" in ic:
        return "MEN"
    return ""


def _add_new_naming_columns(df):
    """Purono column theke notun naming-er (SS27) column bananu.
    Purono column gulo (Size, Product_name, TC_Number_st1, Barcode_st1) thakche."""
    df["Product_name_st"] = df.get("Product_name", "")
    return df


def _order_columns(df):
    first = [c for c in FINAL_COLS if c in df.columns]
    rest = [c for c in df.columns if c not in first and c not in _HIDDEN_COLS]
    return df[first + rest]


def enrich_dataframe(base_df: pd.DataFrame, detected_pl: str = "") -> pd.DataFrame:
    """base_df = extractor-er output. UI dekhay, notun column shoho df return kore.
    Kono reference data (Google Sheet) load na hole base_df-i (shudhu naming
    column shoho) return hoy — label generation kokhono block hoy na."""
    df = _add_new_naming_columns(base_df.copy())

    with st.expander("➕ Additional Data", expanded=True):
        translations_df = load_product_translations()
        if translations_df.empty:
            st.warning("Product translation sheet load hoyni — notun column gulo (product_name, price ...) ekhon khali thakbe.")
            return _order_columns(df)

        # ----- Collection: name mapping (B/G suffix pore) -----
        df["Collection"] = df.apply(
            lambda r: map_collection_name(r.get("Collection", ""), r.get("Item_classification", "")), axis=1
        )

        first_row = df.iloc[0].to_dict() if len(df) else {}
        pdf_item_class = first_row.get("Item_classification", "")
        pdf_item_name_en = re.sub(r"^\d+\.\s*", "", (first_row.get("Item_name_EN") or "").strip()).strip()

        # ============ Department / Product / Washing / PLN ============
        c1, c2, c3, c4 = st.columns(4)

        depts = translations_df["DEPARTMENT"].dropna().unique().tolist()
        default_dept = map_item_class_to_dept_label(pdf_item_class)
        dept_idx = 0
        if default_dept:
            for i, d in enumerate(depts):
                if str(d).strip().lower() == str(default_dept).strip().lower():
                    dept_idx = i
                    break
        with c1:
            selected_dept = st.selectbox("Select Department", options=depts, index=dept_idx, key="ui_dept")

        filtered = translations_df[translations_df["DEPARTMENT"] == selected_dept]
        products = filtered["PRODUCT_NAME"].dropna().unique().tolist()
        prod_idx = 0
        if pdf_item_name_en:
            for i, p in enumerate(products):
                if str(p).strip().lower() == pdf_item_name_en.lower():
                    prod_idx = i
                    break
        with c2:
            product_type = st.selectbox("Select Product Type", options=products, index=prod_idx, key="ui_product")

        wash_opts = list(WASHING_CODES.keys())
        wash_idx = wash_opts.index("9") if "9" in wash_opts else 0
        with c3:
            wash_key = st.selectbox("Select Washing Code", options=wash_opts, index=wash_idx, key="ui_wash")

        with c4:
            pln_raw = st.text_input("Enter PLN Price", value=str(detected_pl or ""), key="ui_pln_price")
        pln_price = parse_pln_price(pln_raw)

        # ============ Material Composition + Care ============
        composition_ctx = render_composition_care_section()

    # ============ Column enrichment ============
    df["Dept"] = df["Item_classification"].apply(_get_dept_value)
    df["Cotton"] = composition_ctx["cotton_value"]
    df["Collection"] = df.apply(
        lambda r: modify_collection(r["Collection"], r.get("Item_classification", "")), axis=1
    )

    product_row = filtered[filtered["PRODUCT_NAME"] == product_type]
    df["product_name"] = (
        format_product_translations(product_type, product_row.iloc[0], composition_ctx)
        if not product_row.empty else ""
    )
    df["washing_code"] = WASHING_CODES[wash_key]
    df["Composition_Care"] = composition_ctx["composition_care_text"]

    # Price ladder: PLN paoa na gele column khali thake, kaj block hoy na
    if pln_price is not None:
        if not apply_price_columns(df, pln_price):
            st.warning("⚠️ PLN price sheet-e pawa jayni — price column gulo khali.")

    return _order_columns(df)
