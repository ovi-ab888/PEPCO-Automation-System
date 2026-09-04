import sys
import os
sys.path.append(os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import io
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
import extractor

theme.main_header("PEPCO Label Automation", "Upload PEPCO order/PO PDF and generate labels effortlessly.")

# -------------------------------
# 1. ফাইল আপলোড সেকশন
# -------------------------------
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

def _reset_all():
    for k in list(st.session_state.keys()):
        if k.startswith(("pdf_", "chk_", "size_tag_", "include_size_tag", "hangtag_", "care_", "benefite_")):
            st.session_state.pop(k, None)
    st.session_state.uploader_key += 1

theme.render_stage_banner(1, ["Upload / Extract", "Review", "Select & generate"])
st.button("Upload New File", on_click=_reset_all)

pdf_files = st.file_uploader(
    "Upload PEPCO PDF",
    type=["pdf"],
    accept_multiple_files=True,
    key=f"pdf_uploader_{st.session_state.uploader_key}",
)

if not pdf_files:
    st.info("Please upload a PDF to continue.")
    st.stop()

# -------------------------------
# 2. ডেটা এক্সট্রাকশন
# -------------------------------
if (
    "pdf_extracted_df" not in st.session_state
    or st.session_state.get("pdf_uploader_names") != [f.name for f in pdf_files]
):
    with st.spinner("Extracting data from PDF..."):
        extracted_df = extractor.extract_rows_from_pdfs(pdf_files)

    if extracted_df.empty:
        st.error("Couldn't extract data from this PDF — check it's the right file type.")
        st.stop()

    extracted_df["Designer"] = auth.get_display_name()  # from the logged-in user, editable below

    st.session_state["pdf_filename_row"] = extracted_df.iloc[0].to_dict()
    st.session_state["pdf_extracted_df"] = extracted_df.drop(columns=["_temp_sku_for_filename"])
    st.session_state["pdf_uploader_names"] = [f.name for f in pdf_files]

# -------------------------------
# 3. ডেটা এডিটর
# -------------------------------
theme.render_stage_banner(2, ["Upload / Extract", "Review", "Select & generate"])

corrected_df = st.data_editor(
    st.session_state["pdf_extracted_df"],
    use_container_width=True,
    num_rows="fixed",
    key="pdf_data_editor",
)

# -------------------------------
# 4. লেবেল টাইপ সিলেক্ট ও জেনারেশন
# -------------------------------
theme.render_stage_banner(3, ["Upload / Extract", "Review", "Select & generate"])

# name -> {"generate": callable(rows) -> pdf_bytes,
#          "template_path": str or None,  (used to derive the filename's template-name part)
#          "template_name": str or None}  (explicit override, e.g. for auto-size types with no single path)
label_options = {
    "Inner & Outer Sticker": {
        "generate": pad_label.generate_batch,
        "template_path": getattr(pad_label, "TEMPLATE_PATH", None),
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

# ---- Section 1: Benefite Tag and Sticker (LIVE) ----
with st.expander("Benefite Tag and Sticker", expanded=True):
    if st.checkbox("Inner & Outer Sticker", key="chk_inner_outer"):
        selected_labels.append("Inner & Outer Sticker")

    sticker_types = benefite_label.list_sticker_types()
    if not sticker_types:
        st.caption("No other Benefite templates found yet in templates/Benefite/.")

    for sticker_type in sticker_types:
        if benefite_label.is_auto_size_type(sticker_type):
            # one checkbox — the right variant is picked per-row automatically
            # by matching each row's Sizes against the available filenames
            col1, col2 = st.columns([2, 2])
            checked = col1.checkbox(sticker_type, key=f"chk_benefite_{sticker_type}")
            with col2:
                theme.render_badge("Auto size")

            if checked:
                for r in corrected_df.to_dict(orient="records"):
                    picked = benefite_label.pick_variant_for_row(sticker_type, r)
                    st.caption(f"[{sticker_type}] Sizes: {r.get('Sizes')} → picked: {picked}")

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

# ---- Section 2: Size Tag (LIVE) ----
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

# ---- Section 3: Hangtag (UI ONLY — not wired up yet) ----
with st.expander("Hangtag", expanded=False):
    theme.render_badge("Coming soon", muted=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.text_input("Enter Composition", key="hangtag_composition", disabled=True)
    c2.text_input("Enter Price", key="hangtag_price", disabled=True)
    c3.selectbox("Select Washing Code", [""], key="hangtag_washing", disabled=True)
    c4.selectbox("Select Product Type", [""], key="hangtag_product_type", disabled=True)

# ---- Section 4: Care Label (UI ONLY — not wired up yet) ----
with st.expander("Care Label", expanded=False):
    theme.render_badge("Coming soon", muted=True)
    c1, c2 = st.columns(2)
    c1.text_input("Enter Composition", key="care_composition", disabled=True)
    c2.selectbox("Select Washing Code", [""], key="care_washing", disabled=True)

if selected_labels and st.button("Generate Selected Labels", type="primary"):
    rows = corrected_df.to_dict(orient="records")

    filename_row = dict(st.session_state.get("pdf_filename_row", {}))
    filename_row.update(rows[0])

    with st.spinner(f"Generating {len(selected_labels)} label type(s)..."):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for label_name in selected_labels:
                entry = label_options[label_name]
                pdf_bytes = entry["generate"](rows)

                template_name = _template_name_for(entry)
                final_filename = extractor.build_filename(
                    filename_row, extension="pdf", template_name=template_name
                )
                zip_file.writestr(final_filename, pdf_bytes)

        zip_buffer.seek(0)

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
