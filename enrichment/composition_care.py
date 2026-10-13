# swingtag_csv/composition_care.py — ported as-is from the SS27 project (no import-path changes needed).
# ================================================================
#  composition_care.py
#  "Composition_Care" CSV column banano — Material Composition (multi
#  component, advanced mode) + Care Instructions + fixed Shrinkage/
#  Bangladesh text, sob mile ekta boro text block.
#
#  NOTE: Composition_Care.py-er WASHING_CODES ei file-e nai — app.py-er
#  nijer washing_code UI ar constants.py-er WASHING_CODES aage-i ache.
#
#  app.py te use korte:
#      from composition_care import render_composition_care_section
# ================================================================
import pandas as pd
import streamlit as st


# ================================================================
#  Text case helper
# ================================================================
def to_sentence_case(text: str) -> str:
    """Convert any text to Sentence Case"""
    if not text or not isinstance(text, str):
        return text
    text = text.strip()
    if not text:
        return text
    return text[0].upper() + text[1:].lower() if len(text) > 1 else text.upper()


# ================================================================
#  DATA LOADERS (Google Sheet)
# ================================================================
@st.cache_data(ttl=600)
def load_care_composition_data():
    BASE_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQtV5x4B3Sf_CCIMLCfvPtSP8nYru5BMAh5Xe4wWkqcrzZqT2cRJ7JYlvaHrsXql0h9Dnqohvq2mrKM/pub"

    sheets_config = {
        "materials": {"url": f"{BASE_URL}?gid=1935147264&single=true&output=csv"},
        "care_instructions": {"url": f"{BASE_URL}?gid=21483732&single=true&output=csv"},
        "component_names": {"url": f"{BASE_URL}?gid=0&single=true&output=csv"}
    }

    result = {}
    for key, config in sheets_config.items():
        try:
            df = pd.read_csv(config["url"])
            result[key] = df if not df.empty else pd.DataFrame()
        except Exception:
            result[key] = pd.DataFrame()
    return result


@st.cache_data(ttl=600)
def load_component_translations():
    care_data = load_care_composition_data()
    if not care_data["component_names"].empty:
        return care_data["component_names"]
    return pd.DataFrame({
        "EN": ["Main fabric", "Lining", "Pocket bag", "Trim", "Hood", "Collar", "Cuff", "Rib"],
        "AL": ["Pëlhurë kryesore", "Llastik", "Thes me xhepa", "Shkurtim", "Kapuç", "Jakë", "Manshetë", "Rib"],
        "BG": ["Основен плат", "Подплата", "Вътрешен джоб", "Подстригване", "Качулка", "Яка", "Маншет", "Rib"]
    })


# ================================================================
#  Fixed text blocks (shob somoy CSV te thake)
# ================================================================
SHRINKAGE_LINE = "Skupljanje:  po dužini: 4%, po širini 4%"

BANGLADESH_LINE = """Made in Bangladesh/ Vendi i Origjinës: Bangladesh/ Произведено в Бангладеш/ Fabricado en Bangladesh/ Κατασκευάζεται στην Μπαγκλαντές/ Pagaminta Bangladeše/ Ražots Bangladešā/ Wyprodukowano w Bangladeszu/ Произведено во Бангладеш/ Proizvedeno u Bangladešu/ Zemlja izvoza: EU/ Виготовлено в Бангладеш.

Produced by/ Prodhuesi/ Производител/ Výrobce/ Hersteller/ Tootja/ Fabricante/
Fabricant/ Κατασκευαστής/ Proizvođač/ Gyártó/ Produttore/ Gamintojas/ Ražotājs/ Producent/ Producător/ Izdelovalec/ Výrobca/ Виробник:

Pepco Poland Sp. z o.o., ul. Strzeszyńska 73A, 60-479 Poznań Poland, klient@pepco.eu, NIP (NIF) 782-21-31-157.
Пепко Полска Сп. з o.o., ул. Стрзесзинска 73А, 60-479 Познан. Пепко Польска Сп. з.о.о., вул Стшешинська 73A, 60-479 Познань. Na tržište RH stavlja: Pepco Croatia d.o.o., D. T. Gavrana 11, 10020 Zagreb.
Uvoznik za Srbiju: Pepco d.o.o., Pariske komune 22, 11070 Beograd-Novi Beograd. klijent.rs@pepco.eu
Διανομέας: Pepco Greece Μονοπρόσωπη Ι.Κ.Ε., Πέτρου Ράλλη 97, 182 33, Αγ. Ιωάννης Ρέντης. Uvoznik za BiH: Pepco B-H d.o.o., ulica Skenderpašina br. 1, Opština Centar Sarajevo, 71 000 Sarajevo. klijent.ba@pepco.eu
Увозник/ Importuesi: ПЕПЦО ДООЕЛ Скопје, Ул. НАУМ НАУМОВСКИ - БОРЧЕ Бр.40/5-8 СКОПЈЕ - ЦЕНТАР ЦЕНТАР/ PEPCO DOOEL Shkup, Rruga Naum Naumovski-Borche Nr. 40/5-8, Shkup – Qendër, Maqedonia e Veriut. Імпортер: ТОВАРИСТВО З ОБМЕЖЕНОЮ ВІДПОВІДАЛЬНІСТЮ “ПЕПКО УКРАЇНА” вул. Загородня, 15,
м. Київ, 03150, Україна, customer@pepco.eu"""


# ================================================================
#  Main UI section
#  Material Composition (multi-component/advanced mode) + Care
#  Instructions dekhay, sob mile "Composition_Care" text return kore.
#  Session-state key shob "cc_" prefix diye (onno UI-r shathe conflict
#  hobe na, reset button diye clear kora jay).
# ================================================================
def render_composition_care_section():
    care_data = load_care_composition_data()
    comp_translations_df = load_component_translations()

    # ---------- Material Composition ----------
    st.markdown("### Material Composition %")

    materials_df = care_data.get("materials", pd.DataFrame())

    materials_options = []
    if not materials_df.empty:
        en_col = materials_df.columns[0]
        materials_options = materials_df[en_col].dropna().astype(str).tolist()
    if not materials_options:
        materials_options = ["Cotton", "Polyester", "Elastane", "Nylon", "Viscose", "Wool"]

    component_options = []
    if not comp_translations_df.empty:
        component_options = comp_translations_df["EN"].dropna().astype(str).tolist()
    if not component_options:
        component_options = ["Main fabric", "Outer fabric", "Lining", "Pocket bag", "Collar", "Cuff", "Rib"]

    use_advanced_mode = st.toggle("Components Mode", value=False, key="cc_use_advanced_mode")

    if "cc_composition_blocks" not in st.session_state:
        st.session_state.cc_composition_blocks = []

    if not st.session_state.cc_composition_blocks:
        st.session_state.cc_composition_blocks.append({
            "component_name": "Main fabric",
            "component_name_optional": "",
            "materials": [{"mat": "Cotton", "pct": 100}]  # default: 100% Cotton pre-selected
        })

    def get_material_all_languages(mat_name, pct):
        if materials_df.empty or not mat_name:
            return f"{pct}% {to_sentence_case(mat_name)}"
        en_col = materials_df.columns[0]
        row = materials_df[materials_df[en_col].astype(str).str.strip() == mat_name]
        if row.empty:
            return f"{pct}% {to_sentence_case(mat_name)}"
        translations = [to_sentence_case(mat_name)]
        for col in materials_df.columns:
            val = row.iloc[0].get(col, "")
            if pd.notna(val) and str(val).strip() and val != mat_name:
                text = str(val).strip()
                translations.append(to_sentence_case(text))
        return f"{pct}% {'/ '.join(translations)}"

    def get_component_name_translations(comp_name):
        if not comp_name or comp_translations_df.empty:
            return to_sentence_case(comp_name) if comp_name else comp_name
        row = comp_translations_df[comp_translations_df['EN'].astype(str).str.strip() == comp_name]
        if row.empty:
            return to_sentence_case(comp_name)
        translations = [to_sentence_case(comp_name)]
        for col in comp_translations_df.columns:
            if col != 'EN':
                val = row.iloc[0].get(col, "")
                if pd.notna(val) and str(val).strip():
                    translations.append(to_sentence_case(str(val).strip()))
        return "/ ".join(translations)

    def build_material_line(materials):
        parts = []
        for m in materials:
            if m["mat"] and m["pct"] > 0:
                mat_text = get_material_all_languages(m["mat"], m["pct"])
                parts.append(mat_text)
        return "\n\n".join(parts)

    components_data = []

    for block_idx, block in enumerate(st.session_state.cc_composition_blocks):
        with st.container(border=True):
            top1, top2 = st.columns([5, 1])
            with top1:
                if use_advanced_mode:
                    # Component Name + Optional Component Name (Same Line)
                    col_name1, col_name2 = st.columns(2)

                    with col_name1:
                        current_name = block.get("component_name", "Main fabric")
                        name_index = component_options.index(current_name) if current_name in component_options else 0
                        block["component_name"] = st.selectbox(
                            f"Component Name #{block_idx + 1}",
                            options=component_options,
                            index=name_index,
                            key=f"cc_comp_name_{block_idx}"
                        )

                    with col_name2:
                        optional_options = [""] + component_options
                        current_optional = block.get("component_name_optional", "")
                        optional_index = optional_options.index(current_optional) if current_optional in optional_options else 0
                        block["component_name_optional"] = st.selectbox(
                            f"Optional Component Name #{block_idx + 1}",
                            options=optional_options,
                            index=optional_index,
                            key=f"cc_comp_name_optional_{block_idx}"
                        )
                else:
                    st.markdown("#### Simple Composition")
            with top2:
                if len(st.session_state.cc_composition_blocks) > 1:
                    st.write("")
                    st.write("")
                    if st.button("🗑️", key=f"cc_remove_block_{block_idx}"):
                        st.session_state.cc_composition_blocks.pop(block_idx)
                        st.rerun()

            st.markdown("#### Materials")
            for mat_idx, mat in enumerate(block["materials"]):
                c1, c2, c3 = st.columns([3, 1.5, 0.7])
                with c1:
                    mat_options = [""] + materials_options
                    mat_index = mat_options.index(mat["mat"]) if mat["mat"] in mat_options else 0
                    mat["mat"] = st.selectbox(
                        "Material",
                        options=mat_options,
                        index=mat_index,
                        key=f"cc_mat_{block_idx}_{mat_idx}"
                    )
                with c2:
                    mat["pct"] = st.number_input(
                        "%",
                        min_value=0,
                        max_value=100,
                        step=1,
                        value=int(mat["pct"]),
                        key=f"cc_pct_{block_idx}_{mat_idx}"
                    )
                with c3:
                    st.write("")
                    if len(block["materials"]) > 1:
                        if st.button("❌", key=f"cc_remove_mat_{block_idx}_{mat_idx}"):
                            block["materials"].pop(mat_idx)
                            st.rerun()

            if st.button("➕ Add Material", key=f"cc_add_material_{block_idx}"):
                block["materials"].append({"mat": "", "pct": 0})
                st.rerun()

            valid_materials = [m for m in block["materials"] if m["mat"] and m["pct"] > 0]
            total_pct = sum(m["pct"] for m in valid_materials)

            if total_pct == 100:
                st.success(f"✅ Total = {total_pct}%")
            elif total_pct < 100 and total_pct > 0:
                st.warning(f"⚠️ Remaining = {100 - total_pct}%")
            elif total_pct > 100:
                st.error(f"❌ Exceeded by {total_pct - 100}%")
            else:
                st.info("📌 Enter material composition")

            if valid_materials and total_pct == 100:
                components_data.append({
                    "name": block["component_name"],
                    "name_optional": block.get("component_name_optional", ""),
                    "materials": valid_materials.copy()
                })

    if use_advanced_mode:
        if len(st.session_state.cc_composition_blocks) < 5:
            if st.button("➕ Add Component", key="cc_add_component_btn"):
                st.session_state.cc_composition_blocks.append({
                    "component_name": "Main fabric",
                    "component_name_optional": "",
                    "materials": [{"mat": "", "pct": 0}]
                })
                st.rerun()
        else:
            st.info("Maximum 5 components allowed")

    # Build composition text
    composition_lines = []
    for comp in components_data:
        material_text = build_material_line(comp["materials"])

        if use_advanced_mode:
            main_name = get_component_name_translations(comp["name"])
            optional_name = get_component_name_translations(comp["name_optional"]) if comp.get("name_optional") else ""

            if optional_name:
                line = f"{main_name}\n\n{optional_name}:\n\n{material_text}"
            else:
                line = f"{main_name}:\n\n{material_text}"
        else:
            line = material_text

        composition_lines.append(line)

    final_composition_text = "\n\n".join(composition_lines)

    # ---------- Care Instructions ----------
    st.markdown("### Care Instructions")

    care_instructions_df = care_data.get("care_instructions", pd.DataFrame())

    if "cc_care_inst_list" not in st.session_state:
        st.session_state.cc_care_inst_list = []

    care_inst_options = []
    if not care_instructions_df.empty:
        en_col = care_instructions_df.columns[0]
        care_inst_options = care_instructions_df[en_col].dropna().astype(str).tolist()

    if st.session_state.cc_care_inst_list:
        st.write("**Selected Care Instructions:**")
        for idx, selected in enumerate(st.session_state.cc_care_inst_list):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"• {selected}")
            with col2:
                if st.button("Remove", key=f"cc_remove_care_{idx}"):
                    st.session_state.cc_care_inst_list.pop(idx)
                    st.rerun()

    col_add_care, _ = st.columns([2, 3])
    with col_add_care:
        new_care_inst = st.selectbox("Add Care Instruction", options=[""] + care_inst_options, key="cc_new_care_inst_select")
        if st.button("Add Care Instruction", key="cc_add_care_inst_btn"):
            if new_care_inst and new_care_inst not in st.session_state.cc_care_inst_list:
                st.session_state.cc_care_inst_list.append(new_care_inst)
                st.rerun()
            elif new_care_inst in st.session_state.cc_care_inst_list:
                st.warning("This instruction already added!")

    def get_care_instruction_all_languages(inst_text, care_instructions_df):
        if not inst_text or care_instructions_df.empty:
            return ""
        en_col = care_instructions_df.columns[0]
        row = care_instructions_df[care_instructions_df[en_col].astype(str).str.strip() == inst_text]
        if row.empty:
            return to_sentence_case(inst_text)
        translations = []
        for col in care_instructions_df.columns:
            val = row.iloc[0].get(col, "")
            if pd.notna(val) and str(val).strip():
                translations.append(to_sentence_case(str(val).strip()))
        return "/ ".join(translations)

    all_care_inst_translated = []
    for selected_care_inst in st.session_state.cc_care_inst_list:
        inst_text = get_care_instruction_all_languages(selected_care_inst, care_instructions_df)
        if inst_text:
            all_care_inst_translated.append(inst_text)

    care_inst_translated = "\n\n".join(all_care_inst_translated) if all_care_inst_translated else ""

    # ---------- Build Composition_Care ----------
    combined_care = ""
    if final_composition_text and care_inst_translated:
        combined_care = f"{final_composition_text}\n\n{care_inst_translated}"
    elif final_composition_text:
        combined_care = final_composition_text
    elif care_inst_translated:
        combined_care = care_inst_translated

    if combined_care:
        combined_care = f"{combined_care}\n\n\n\n\n\n\n\n\n\n{SHRINKAGE_LINE}\n\n\n\n\n\n\n\n\n\n{BANGLADESH_LINE}"
    else:
        combined_care = f"{SHRINKAGE_LINE}\n\n\n\n\n\n\n\n\n\n{BANGLADESH_LINE}"

    # ---------- Cotton flag (CSV "Cotton" column) ----------
    # Shudhu ekta component ar tar bhitore ekta-i material thakle, ar sheta
    # 100% Cotton hole "Z" — na hole khali. (Simple Mode-e ei-i case.)
    cotton_value = get_cotton_value(components_data)

    # ---------- product_name (AL/MK)-er jonno context return kora ----------
    # Eta translation.py-er format_product_translations()-ke pathano hoy,
    # jate product_name-er composition ar ei Composition_Care-er composition
    # EK-I data theke ashe (double input lage na).
    return {
        "composition_care_text": combined_care,
        "cotton_value": cotton_value,
        "components_data": components_data,
        "materials_df": materials_df,
        "comp_translations_df": comp_translations_df,
        "use_advanced_mode": use_advanced_mode,
    }


# ================================================================
#  Ekta component-er Cotton flag ber kora
#  Shudhu 1-ta component + shei component-e 1-ta-i material (100% Cotton)
#  hole "Z", na hole khali.
# ================================================================
def get_cotton_value(components_data):
    if len(components_data) == 1 and len(components_data[0]["materials"]) == 1:
        m = components_data[0]["materials"][0]
        mat_name = (m.get("mat") or "").strip().lower()
        try:
            pct = int(m.get("pct") or 0)
        except (TypeError, ValueError):
            pct = 0
        if mat_name == "cotton" and pct == 100:
            return "Z"
    return ""


# ================================================================
#  Ekta material-er naam EKTA nirdishto language-e (jemon shudhu "AL")
# ================================================================
def _material_name_in_language(mat_name, materials_df, lang):
    if not mat_name:
        return ""
    if materials_df.empty:
        return to_sentence_case(mat_name)

    en_col = materials_df.columns[0]
    row = materials_df[materials_df[en_col].astype(str).str.strip() == mat_name]
    if row.empty or lang not in materials_df.columns:
        return to_sentence_case(mat_name)

    val = row.iloc[0].get(lang, "")
    if pd.notna(val) and str(val).strip():
        return to_sentence_case(str(val).strip())
    return to_sentence_case(mat_name)


# ================================================================
#  Ekta component-er naam EKTA nirdishto language-e (jemon shudhu "AL")
# ================================================================
def _component_name_in_language(comp_name, comp_translations_df, lang):
    if not comp_name:
        return ""
    if comp_translations_df.empty or lang not in comp_translations_df.columns:
        return to_sentence_case(comp_name)

    row = comp_translations_df[comp_translations_df['EN'].astype(str).str.strip() == comp_name]
    if row.empty:
        return to_sentence_case(comp_name)

    val = row.iloc[0].get(lang, "")
    if pd.notna(val) and str(val).strip():
        return to_sentence_case(str(val).strip())
    return to_sentence_case(comp_name)


# ================================================================
#  product_name (AL/MK)-er jonno composition text banano — EK-I
#  components_data theke, jeta Composition_Care o use kore.
#
#  Simple Mode: "100% Pambuk" (component name chara)
#  Advanced Mode, ekta component: "Pëlhurë kryesore 100% Pambuk"
#  Advanced Mode, multi component:
#     "Pëlhurë kryesore 100% Pambuk: Llastik 95% Pambuk, 5% Elasten"
#
#  app.py/translation.py te use korte:
#      from composition_care import build_language_composition
# ================================================================
def build_language_composition(components_data, materials_df, comp_translations_df, lang, use_advanced_mode):
    parts = []
    for comp in components_data:
        mat_parts = [
            f"{m['pct']}% {_material_name_in_language(m['mat'], materials_df, lang)}"
            for m in comp["materials"]
        ]
        materials_str = ", ".join(mat_parts)

        if use_advanced_mode:
            comp_name = _component_name_in_language(comp["name"], comp_translations_df, lang)
            parts.append(f"{comp_name} {materials_str}" if comp_name else materials_str)
        else:
            parts.append(materials_str)

    return ": ".join(parts)
