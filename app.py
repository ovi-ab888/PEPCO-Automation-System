import sys
import os
sys.path.append(os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import io
import csv
import json
import zipfile

import theme
import auth

# পেজ কনফিগারেশন
st.set_page_config(page_title="PEPCO Label Automation", layout="wide")
theme.load_css()  # login page-ও এই style পাবে

# -------------------------------
# 0. লগইন চেক (সবার আগে)
# -------------------------------
if not auth.check_login():
    st.stop()

auth.logout_button()

# সব লেবেল জেনারেটর মডিউল ইমপোর্ট করুন
import labels.pad_label as pad_label
import labels.inner_label as inner_label
import labels.outer_label as outer_label
import labels.benefite as benefite_label
import labels.size_tag as size_tag_label
import labels.hangtag_pad as hangtag_pad  # Hangtag (Front+Back+Pad) — table theke data
import labels.care_label as care_label  # Care Label (Front1 + Composition flow + Pad) — table theke data
import extractor
from enrichment.enrich import enrich_dataframe

theme.main_header("PEPCO Label Automation", "Upload PEPCO order/PO PDF and generate labels effortlessly.")

# -------------------------------
# 1. ফাইল আপলোড সেকশন
# -------------------------------
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0


def _reset_all():
    for k in list(st.session_state.keys()):
        if k.startswith(("pdf_", "chk_", "size_tag_", "include_size_tag", "hangtag_", "care_", "benefite_", "ui_", "cc_")):
            st.session_state.pop(k, None)
    st.session_state.uploader_key += 1


st.button("Upload New File", on_click=_reset_all)

pdf_files = st.file_uploader(
    "Upload PEPCO PDF",
    type=["pdf"],
    accept_multiple_files=True,
    key=f"pdf_uploader_{st.session_state.uploader_key}",
)
if not pdf_files:
    st.stop()

# -------------------------------
# 1b. Missing-data helpers (extractor fail korle user-er kach theke input)
# -------------------------------
GLOBAL_REQUIRED = {  # PDF-er shob row-e same value
    "Order_ID": "Order ID",
    "Style": "Style (Item No)",
    "Colour": "Colour",
    "Item_name_English": "Item name (English)",
    "Season": "Season (e.g. SS27)",
    "Collection": "Collection name",
    "Supplier_name": "Supplier name",
}
ROW_REQUIRED = {  # row-wise alada value
    "Sizes": "Size",
    "SKU": "SKU",
    "barcode": "Barcode",
}
_MISSING = {"", "UNKNOWN", "NAN", "NONE", "NULL"}

# Manual-entry fallback table-er columns (extractor-er row key-er sathe milano)
MANUAL_COLUMNS = [
    "Order_ID", "Style", "Colour", "Supplier_product_code", "Item_classification",
    "Supplier_name", "today_date", "Item_name_English", "Item_name_EN", "Season",
    "Sizes", "Collection", "Colour_SKU", "Style_Merch_Season", "Batch", "SKU",
    "barcode", "cm_size",
]


def _is_missing(v) -> bool:
    if pd.isna(v):
        return True
    s = str(v).strip()
    # blank / UNKNOWN, ba extractor vul kore PDF-er label ("Pictogram no .....") tule nile
    return s.upper() in _MISSING or "..." in s


def _store_extracted(df, names):
    """Extracted (ba manual) df ke session-e rakhe — original flow-er moto."""
    df = df.reset_index(drop=True)
    for c in list(GLOBAL_REQUIRED) + list(ROW_REQUIRED):
        if c not in df.columns:
            df[c] = ""
    if "_temp_sku_for_filename" not in df.columns:
        df["_temp_sku_for_filename"] = "MANUAL"
    if "_pl_price_detected" not in df.columns:
        df["_pl_price_detected"] = ""
    df["Designer"] = auth.get_display_name()  # from the logged-in user, editable below
    st.session_state["pdf_group_keys"] = (
        df["_temp_sku_for_filename"].fillna("MANUAL").astype(str).tolist()
    )
    st.session_state["pdf_filename_row"] = df.iloc[0].to_dict()
    st.session_state["pdf_pl_price"] = df["_pl_price_detected"].iloc[0]
    st.session_state["pdf_extracted_df"] = df.drop(
        columns=["_temp_sku_for_filename", "_pl_price_detected"]
    )
    st.session_state["pdf_uploader_names"] = names
    st.session_state["pdf_df_version"] = st.session_state.get("pdf_df_version", 0) + 1


def _manual_entry_fallback(names):
    """Extractor PDF-e puro fail korle: user nijei data lekhe."""
    st.error("Extractor couldn't read this PDF automatically. Please enter the data below.")
    blank = pd.DataFrame([{c: "" for c in MANUAL_COLUMNS}])
    with st.form("pdf_manual_form"):
        edited = st.data_editor(
            blank, num_rows="dynamic", use_container_width=True, key="pdf_manual_editor"
        )
        ok = st.form_submit_button("Use this data")
    if ok:
        edited = edited.fillna("")
        edited = edited[edited.apply(lambda r: any(str(v).strip() for v in r), axis=1)]
        if edited.empty:
            st.warning("Please fill at least one row.")
        else:
            edited = edited.copy()
            edited["_temp_sku_for_filename"] = "MANUAL"
            _store_extracted(edited, names)
            st.rerun()
    st.stop()


def _find_missing(df) -> dict:
    out = {}
    for col in list(GLOBAL_REQUIRED) + list(ROW_REQUIRED):
        if col not in df.columns:
            continue
        idx = [i for i, v in df[col].items() if _is_missing(v)]
        if idx:
            out[col] = idx
    return out


def _render_missing_section(df) -> bool:
    """Missing field thakle user-er kach theke input ney.
    True = shob thik (ba user 'continue anyway' chose korse) -> flow cholbe."""
    missing = _find_missing(df)
    if not missing:
        return True

    keys = st.session_state.get("pdf_group_keys", [])
    if len(keys) != len(df):
        keys = [str(i) for i in range(len(df))]
    groups = {}
    for i, k in enumerate(keys):
        groups.setdefault(k, []).append(i)

    st.warning("Some data couldn't be extracted from the PDF. Please fill in the missing fields.")

    with st.form("pdf_missing_form"):
        inputs = {}
        for g_no, (gk, idxs) in enumerate(groups.items(), start=1):
            g_missing = [
                c for c in GLOBAL_REQUIRED
                if c in missing and any(i in missing[c] for i in idxs)
            ]
            if not g_missing:
                continue
            first_oid = df.loc[idxs[0], "Order_ID"] if "Order_ID" in df.columns else ""
            title = f"PDF {g_no}" + ("" if _is_missing(first_oid) else f" — {first_oid}")
            st.markdown(f"**{title}**")
            cols = st.columns(min(3, len(g_missing)))
            for j, c in enumerate(g_missing):
                with cols[j % len(cols)]:
                    inputs[(gk, c)] = st.text_input(
                        GLOBAL_REQUIRED[c], key=f"pdf_missing_{g_no}_{c}"
                    )

        row_cols = [c for c in ROW_REQUIRED if c in missing]
        row_editor = None
        if row_cols:
            row_idx = sorted({i for c in row_cols for i in missing[c]})
            st.markdown("**Row-wise missing values**")
            sub = df.loc[row_idx, row_cols].copy()
            for c in row_cols:
                sub[c] = sub[c].apply(lambda v: "" if _is_missing(v) else str(v))
            row_editor = st.data_editor(
                sub, num_rows="fixed", use_container_width=True, key="pdf_missing_row_editor"
            )
        submitted = st.form_submit_button("Apply")

    if submitted:
        new = df.copy()
        for (gk, c), val in inputs.items():
            val = (val or "").strip()
            if not val:
                continue
            for i in groups[gk]:
                if _is_missing(new.at[i, c]):
                    new.at[i, c] = val
        if row_editor is not None:
            for i in row_editor.index:
                for c in row_cols:
                    v = str(row_editor.at[i, c]).strip()
                    if v and not _is_missing(v):
                        new.at[i, c] = v
        st.session_state["pdf_extracted_df"] = new
        st.session_state["pdf_df_version"] = st.session_state.get("pdf_df_version", 0) + 1
        st.rerun()

    return st.checkbox("Continue with blank fields anyway", key="pdf_skip_missing")

# -------------------------------
# 2. ডেটা এক্সট্রাকশন
# -------------------------------
if (
    "pdf_extracted_df" not in st.session_state
    or st.session_state.get("pdf_uploader_names") != [f.name for f in pdf_files]
):
    _names = [f.name for f in pdf_files]
    with st.spinner("Extracting data from PDF..."):
        try:
            extracted_df = extractor.extract_rows_from_pdfs(pdf_files)
        except Exception as e:
            st.warning(f"Extractor error: {e}")
            extracted_df = pd.DataFrame()
    if extracted_df is None or extracted_df.empty:
        _manual_entry_fallback(_names)  # st.stop() inside
    _store_extracted(extracted_df, _names)

# Missing field thakle user-er kach theke input chao
if not _render_missing_section(st.session_state["pdf_extracted_df"]):
    st.stop()

# -------------------------------
# 3. ডেটা এডিটর
# -------------------------------
enriched_df = enrich_dataframe(
    st.session_state["pdf_extracted_df"], st.session_state.get("pdf_pl_price", "")
)

corrected_df = st.data_editor(
    enriched_df,
    use_container_width=True,
    num_rows="fixed",
    key=f"pdf_data_editor_{st.session_state.get('pdf_df_version', 0)}",
)

# Edit kora Product_name_st ke label-er Product_name e pathao
if "Product_name_st" in corrected_df.columns:
    corrected_df = corrected_df.copy()
    corrected_df["Product_name"] = corrected_df["Product_name_st"]


def _build_table_csv_bytes(df) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL)
    writer.writerow(df.columns.tolist())
    for row in df.itertuples(index=False):
        writer.writerow(row)
    return buf.getvalue().encode("utf-8-sig")


def _build_table_csv_filename(df) -> str:
    filename_row = dict(st.session_state.get("pdf_filename_row", {}))
    if len(df):
        filename_row.update(df.fillna("").iloc[0].to_dict())
    return extractor.build_filename(filename_row, extension="csv", template_name="Data")


st.download_button(
    "📥 Download CSV",
    _build_table_csv_bytes(corrected_df),
    file_name=_build_table_csv_filename(corrected_df),
    mime="text/csv",
)


def _order_rows(rows: list) -> list:
    """Order-level label (Benefite, Size Tag ...) ekta-i hoy, row-wise na.
    1st row-ke base kore "Sizes" = shob row-er size ek-sathe (XS, S, M, L, XL)."""
    if not rows:
        return rows
    sizes = [str(r.get("Sizes", "")).strip() for r in rows]
    joined = ", ".join(dict.fromkeys(s for s in sizes if s))
    base = dict(rows[0])
    base["Sizes"] = joined
    return [base]


# -------------------------------
# 4. লেবেল টাইপ সিলেক্ট ও জেনারেশন
# -------------------------------
st.subheader("Select Label Types to Generate")

# name -> {"generate": callable(rows) -> pdf_bytes,
#          "template_path": str or None,   (used to derive the filename's template-name part)
#          "template_name": str or None}   (explicit override, e.g. for auto-size types with no single path)
label_options = {
    "Inner & Outer Sticker": {
        "generate": pad_label.generate_batch,
        "template_path": getattr(pad_label, "TEMPLATE_PATH", None),
        "per_row": True,  # 1 row (1 size) = 1 page
    },
}

FILENAME_MAPPING_PATH = os.path.join(os.path.dirname(__file__), "config", "filename_mapping.json")
try:
    with open(FILENAME_MAPPING_PATH, "r") as f:
        FILENAME_MAPPING = json.load(f)
except FileNotFoundError:
    FILENAME_MAPPING = {}


def _template_name_for(entry: dict) -> str:
    """The name to use in the download filename for this label type.
    Checks config/filename_mapping.json first (template filename / sticker
    type -> desired download name); falls back to the raw template
    filename (no extension) if there's no mapping entry."""
    if entry.get("template_name"):
        raw_name = entry["template_name"]
    else:
        path = entry.get("template_path")
        raw_name = os.path.splitext(os.path.basename(path))[0] if path else "Sticker"
    return FILENAME_MAPPING.get(raw_name, raw_name)


selected_labels = []

# ---- Block 1: General Items (Inner & Outer Sticker | Hangtag | Care Label — pasa pasi) ----
with st.expander("General Items", expanded=True):
    gi_col1, gi_col2, gi_col3 = st.columns(3)

    # Inner & Outer Sticker
    with gi_col1:
        if st.checkbox("Inner & Outer Sticker", key="chk_inner_outer"):
            selected_labels.append("Inner & Outer Sticker")

    # Hangtag (upor-er editable table theke shorashori data ney)
    hangtag_rows = corrected_df.fillna("").to_dict(orient="records")
    _missing = [c for c in ("product_name", "PLN") if not any(str(r.get(c, "")).strip() for r in hangtag_rows)]

    with gi_col2:
        include_hangtag = st.checkbox("Hangtag", key="chk_hangtag", disabled=bool(_missing))
        if _missing:
            st.caption("Hangtag-er jonno 'Additional Data'-te Department/Product Type ar PLN Price din "
                       f"(ekhono khali: {', '.join(_missing)}).")
    if include_hangtag and not _missing:
        label_options["Hangtag"] = {
            "generate": lambda rows: hangtag_pad.generate_batch_pdf(rows),
            "template_path": None,
            "template_name": "Hangtag",
            "per_row": True,   # hangtag nijei row-gulo group kore
        }
        selected_labels.append("Hangtag")

    # Care Label (upor-er table theke data ney)
    care_rows = corrected_df.fillna("").to_dict(orient="records")
    _care_missing = care_label.missing_columns(care_rows)

    with gi_col3:
        include_care = st.checkbox("Care Label", key="chk_care_label", disabled=bool(_care_missing))
        if _care_missing:
            st.caption("Care Label-er jonno table-e ei column-gulo lagbe (ekhono khali/nei): "
                       f"{', '.join(_care_missing)}")
    if include_care and not _care_missing:
        label_options["Care Label"] = {
            "generate": lambda rows: care_label.generate_batch_pdf(rows),
            "template_path": None,
            "template_name": "Care Label",
            "per_row": True,   # 1 row = 1 size; care_label nijei Pad-e group kore
        }
        selected_labels.append("Care Label")

# ---- Block 2: Size Tag (LIVE) ----
with st.expander("Size Tag", expanded=False):
    size_types = size_tag_label.list_types()
    if not size_types:
        st.caption("No Size Tag templates found yet in templates/Sizetag/.")
    else:
        c1, c2, c3, c4 = st.columns(4)

        sel_type = c1.selectbox("Select Type", size_types, key="size_tag_type")

        departments = size_tag_label.list_departments(sel_type) if sel_type else []
        sel_dept = c2.selectbox("Select Department", departments, key="size_tag_dept") if departments else None

        customers = size_tag_label.list_customers(sel_type, sel_dept) if sel_dept else []
        sel_cust = c3.selectbox("Select Customer", customers, key="size_tag_cust") if customers else None

        sizes = size_tag_label.list_sizes(sel_type, sel_dept, sel_cust) if sel_cust else []
        sel_size = c4.selectbox("Select Size", sizes, key="size_tag_size") if sizes else None

        include_size_tag = st.checkbox("Generate Size Tag", key="include_size_tag", disabled=not sel_size)
        if include_size_tag and sel_size:
            template_path = size_tag_label.get_template_path(sel_type, sel_dept, sel_cust, sel_size)
            size_tag_key = f"Size Tag ({sel_type}/{sel_dept}/{sel_cust}/{sel_size})"
            label_options[size_tag_key] = {
                "generate": lambda rows, tp=template_path: size_tag_label.generate_batch(rows, tp),
                "template_path": template_path,
            }
            selected_labels.append(size_tag_key)

# ---- Block 3: Benefite Tag and Sticker (templates/Benefite/ theke auto-scan) ----
with st.expander("Benefite Tag and Sticker", expanded=False):
    sticker_types = benefite_label.list_sticker_types()
    if not sticker_types:
        st.caption("No Benefite templates found yet in templates/Benefite/.")
    for sticker_type in sticker_types:
        if benefite_label.is_auto_size_type(sticker_type):
            # one checkbox — the right variant is picked per-row automatically
            # by matching each row's Sizes against the available filenames
            checked = st.checkbox(sticker_type, key=f"chk_benefite_{sticker_type}")
            if checked:
                label_options[sticker_type] = {
                    "generate": lambda rows, st_=sticker_type: benefite_label.generate_batch_auto_size(rows, st_),
                    "template_path": None,
                    "template_name": sticker_type,
                }
                selected_labels.append(sticker_type)
            continue

        variants = benefite_label.list_variants(sticker_type)
        if not variants:
            continue

        col1, col2 = st.columns([2, 2])
        checked = col1.checkbox(sticker_type, key=f"chk_benefite_{sticker_type}")
        if len(variants) > 1:
            sel_variant = col2.selectbox(
                "Select variant", variants,
                key=f"benefite_variant_{sticker_type}", label_visibility="collapsed",
            )
        else:
            sel_variant = variants[0]

        if checked:
            template_path = benefite_label.get_template_path(sticker_type, sel_variant)
            label_key = f"{sticker_type} ({sel_variant})" if len(variants) > 1 else sticker_type
            label_options[label_key] = {
                "generate": lambda rows, tp=template_path: benefite_label.generate_batch(rows, tp),
                "template_path": template_path,
            }
            selected_labels.append(label_key)

if selected_labels and st.button("Generate Selected Labels", type="primary"):
    rows = corrected_df.fillna("").to_dict(orient="records")
    filename_row = dict(st.session_state.get("pdf_filename_row", {}))
    filename_row.update(rows[0])

    with st.spinner(f"Generating {len(selected_labels)} label type(s)..."):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for label_name in selected_labels:
                entry = label_options[label_name]
                label_rows = rows if entry.get("per_row") else _order_rows(rows)
                try:
                    pdf_bytes = entry["generate"](label_rows)
                except care_label.CareLabelOverflow as e:
                    st.error(f"{label_name}: {e}")
                    st.stop()

                template_name = _template_name_for(entry)
                final_filename = extractor.build_filename(
                    filename_row, extension="pdf", template_name=template_name
                )

                zip_file.writestr(final_filename, pdf_bytes)
        zip_buffer.seek(0)

    st.success(f"Done! {len(selected_labels)} label type(s) generated and packaged in a ZIP file.")

    # ZIP filename = Supplier_product_code value
    supplier_code = str(filename_row.get("Supplier_product_code", "UNKNOWN")).strip() or "UNKNOWN"
    zip_name = f"{supplier_code}.zip"

    st.download_button(
        "Download All Labels (ZIP)",
        data=zip_buffer,
        file_name=zip_name,
        mime="application/zip",
        use_container_width=True,
    )

st.markdown(
    '<div class="footer-border" style="padding:14px 0; text-align:center; margin-top:1rem;">'
    '<span class="footer-text">Developed by Ovi | All Rights Reserved. &copy; 2026 PEPCO Automation System</span>'
    '</div>',
    unsafe_allow_html=True,
)
