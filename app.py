import sys
import os
sys.path.append(os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import io
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
import labels.two_pieces_set as pieces_label
import labels.additional_care_instruction_tag as care_tag_label
import labels.look_at_my_back_sticker as back_sticker_label
import labels.two_packs as two_packs_label
import labels.kvi_size_stickers as kvi_label
import labels.size_tag as size_tag_label
import extractor

theme.main_header("PEPCO Label Automation", "Upload PEPCO order/PO PDF and generate labels effortlessly.")

# -------------------------------
# 1. ফাইল আপলোড সেকশন
# -------------------------------
pdf_files = st.file_uploader(
    "Upload PEPCO PDF",
    type=["pdf"],
    accept_multiple_files=True,
    key="pdf_uploader",
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
st.subheader("Review & correct extracted data")
st.caption("Every field is editable — fix anything the extractor got wrong.")
corrected_df = st.data_editor(
    st.session_state["pdf_extracted_df"],
    use_container_width=True,
    num_rows="fixed",
    key="pdf_data_editor",
)

# -------------------------------
# 4. লেবেল টাইপ সিলেক্ট ও জেনারেশন
# -------------------------------
st.subheader("Select Label Types to Generate")

# name -> {"generate": callable(rows) -> pdf_bytes, "template_path": str or None}
label_options = {
    "Inner & Outer Sticker": {
        "generate": pad_label.generate_batch,
        "template_path": getattr(pad_label, "TEMPLATE_PATH", None),
    },
    "2-Pieces-Set": {
        "generate": pieces_label.generate_batch,
        "template_path": getattr(pieces_label, "TEMPLATE_PATH", None),
    },
    "Additional Care Instruction Tag": {
        "generate": care_tag_label.generate_batch,
        "template_path": getattr(care_tag_label, "TEMPLATE_PATH", None),
    },
    "Look at my back Sticker": {
        "generate": back_sticker_label.generate_batch,
        "template_path": getattr(back_sticker_label, "TEMPLATE_PATH", None),
    },
    "Two Packs Sticker": {
        "generate": two_packs_label.generate_batch,
        "template_path": getattr(two_packs_label, "TEMPLATE_PATH", None),
    },
    "KVI Size Sticker - Kids": {
        "generate": lambda rows: kvi_label.generate_batch(rows, size_type="Kids"),
        "template_path": kvi_label.TEMPLATES["Kids"],
    },
    "KVI Size Sticker - Older Top": {
        "generate": lambda rows: kvi_label.generate_batch(rows, size_type="Older Top"),
        "template_path": kvi_label.TEMPLATES["Older Top"],
    },
    "KVI Size Sticker - Older Top Bottom": {
        "generate": lambda rows: kvi_label.generate_batch(rows, size_type="Older Top Bottom"),
        "template_path": kvi_label.TEMPLATES["Older Top Bottom"],
    },
}


def _template_name_for(entry: dict) -> str:
    """The actual template PDF filename (no extension) this label uses —
    e.g. 'Inner_Outer_Sticker' for templates/Inner_Outer_Sticker.pdf. Falls
    back to 'Sticker' if no template_path is available yet."""
    path = entry.get("template_path")
    if not path:
        return "Sticker"
    return os.path.splitext(os.path.basename(path))[0]


selected_labels = []

# ---- Section 1: Benefite Tag and Sticker (LIVE) ----
with st.expander("Benefite Tag and Sticker", expanded=True):
    cols = st.columns(4)
    for i, label_name in enumerate(label_options.keys()):
        with cols[i % 4]:
            if st.checkbox(label_name, key=f"chk_{i}"):
                selected_labels.append(label_name)

# ---- Section 2: Size Tag (LIVE) ----
with st.expander("Size Tag", expanded=False):
    size_tag_variant = st.selectbox("Select Type", ["Regular", "OEKO-TEX"], key="size_tag_variant")
    include_size_tag = st.checkbox("Generate Size Tag", key="include_size_tag")
    if include_size_tag:
        size_tag_key = f"Size Tag ({size_tag_variant})"
        label_options[size_tag_key] = {
            "generate": lambda rows, v=size_tag_variant: size_tag_label.generate_batch(rows, variant=v),
            "template_path": size_tag_label.TEMPLATES[size_tag_variant],
        }
        selected_labels.append(size_tag_key)

# ---- Section 3: Hangtag (UI ONLY — not wired up yet) ----
with st.expander("Hangtag", expanded=False):
    c1, c2, c3, c4 = st.columns(4)
    c1.text_input("Enter Composition", key="hangtag_composition", disabled=True)
    c2.text_input("Enter Price", key="hangtag_price", disabled=True)
    c3.selectbox("Select Washing Code", [""], key="hangtag_washing", disabled=True)
    c4.selectbox("Select Product Type", [""], key="hangtag_product_type", disabled=True)

# ---- Section 4: Care Label (UI ONLY — not wired up yet) ----
with st.expander("Care Label", expanded=False):
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
