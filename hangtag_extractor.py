"""
hangtag_extractor.py
=====================
PEPCO Hangtag (Swingtag) data extraction + enrichment.

Ported from the standalone "PEPCO SS27" app (github.com/ovi-ab888/PEPCO_SS27)
and adapted into a plain, importable module for pepco_test_001.

Design notes:
- Manual-fallback UI (e.g. "Collection not found, enter manually") is NOT
  handled inside this module. Extraction functions return "UNKNOWN" / ""
  when a value can't be found, and app.py (Phase 4) decides whether to
  show a Streamlit text_input fallback. This keeps the extractor testable
  and consistent with the existing extractor.py style.
- The 3 Google Sheet loaders (load_price_data / load_product_translations /
  load_material_translations) fetch LIVE data at runtime — nothing to
  bundle locally. Caching uses st.cache_data when Streamlit is available,
  and falls back to a no-op decorator otherwise (so this module can also
  be imported/tested outside a Streamlit run).
"""

import re
from datetime import datetime, timedelta

import pandas as pd
import requests
import fitz  # PyMuPDF

try:
    import streamlit as st
    _cache_data = st.cache_data
except Exception:  # pragma: no cover - allows import outside Streamlit
    st = None

    def _cache_data(*args, **kwargs):
        def _decorator(fn):
            return fn
        if args and callable(args[0]):
            return args[0]
        return _decorator


# ================================================================
#  WASHING CODES  (key -> pictogram-font-encoded string)
#  Render the returned string using the PEPCO_Ovi.ttf pictogram font
#  (same font already used for the Pictogram/Promotional icon field).
# ================================================================
WASHING_CODES = {
    '1': '১২৩৪৫', '2': '১৪৭৮৫', '3': 'djnst', '4': 'djnpt', '5': 'djnqt',
    '6': 'djnqt', '7': 'gjnpt', '8': 'gjnpu', '9': 'gjnqt', '10': 'gjnqu',
    '11': 'ijnst', '12': 'ijnsu', '13': 'ijnpu', '14': 'ijnsv', '15': 'djnsw',
}


# ================================================================
#  COLLECTION NAME MAPPING (Item_classification group -> {raw: display})
# ================================================================
COLLECTION_MAPPING = {
    # ---------------- Baby Girls ----------------
    "a": {  # baby girls outerwear
        "CUTE BEAR": "MODERN 1",
        "SUMMER CHERRY": "ROMANTIC 1",
        "AUTUMN": "ROMANTIC 2",
    },
    "d_girls": {  # baby girls essentials
        "FLOWER MOUSE": "MODERN 1",
        "LITTEL FOREST": "ROMANTIC 1",
    },
    # ---------------- Baby Boys ----------------
    "b": {  # baby boys outerwear
        "DOGS&FRIENDS": "MODERN 1",
        "EXPOLORE THE MOUNTINE": "MODERN 2",
        "SUMMER FUN": "MODERN 4",
        "COOL TRIP": "CLASSIC 1",
        "COLLEGE BEARS": "CLASSIC 1",
    },
    "d": {  # baby boys essentials
        "DOGS FRIENDS": "CLASSIC 1",
        "FOREST STORY": "MODERN 1",
        "LITTLE DREAMER": "MODERN 1",
        "X-MAS": "CLASSIC 2",
    },
    # ---------------- Younger Girls ----------------
    "yg": {
        "BFF’S CLUB": "COLLECTION_1",
        "LOVELY GIRL": "COLLECTION_2",
        "MEADOWLANDS": "COLLECTION_3",
        "EASTER ELEGANT": "COLLECTION_4",
        "HOT_COUNTRIES_Santorini": "COLLECTION_5",
        "READ_FRUITS": "COLLECTION_6",
        "SEA_SHELLL": "COLLECTION_7",
        "WILD_FOREST": "COLLECTION_7",
    },
    # ---------------- Older Girls ----------------
    "og": {
        "TRANSITIONAL LUMINOUS BLUME": "COLLECTION 1",
        "VALENTINE": "COLLECTION 2",
        "SOUVENIRE SNACK": "COLLECTION 3",
        "MY FAVOURITE THINGS": "COLLECTION 4",
        "CANDY": "COLLECTION 5",
        "SEASIDE": "COLLECTION 6",
        "LE SOLEI": "COLLECTION 7",
        "xxxxx": "COLLECTION 0",
    },
    # ---------------- Younger Boys ----------------
    "yb": {
        "FUNDAY CLUB": "COLLECTION_1",
        "DISCOVER DINO": "COLLECTION_2",
        "DOUBLE-TAKE": "COLLECTION_3",
        "EASTER ELEGANT": "COLLECTION_4",
        "SPORT": "COLLECTION_5",
        "MARITIME": "COLLECTION_6",
        "JUNGLE VIBES": "COLLECTION_7",
        "SURFING": "COLLECTION_8",
    },
    # ---------------- Older Boys ----------------
    "ob": {
        "REBEL RIDER": "COLLECTION 1",
        "SKATE EPIC": "COLLECTION 2",
        "GAMER MODE": "COLLECTION 3",
        "SPORT": "COLLECTION 4",
        "SURFING": "COLLECTION 5",
    },
    # ---------------- Ladies ----------------
    "l": {
        "XXXXX_1": "COLLECTION_1",
        "XXXXX_2": "COLLECTION_2",
        "XXXXX_3": "COLLECTION_3",
        "XXXXX_4": "COLLECTION_4",
        "XXXXX_5": "COLLECTION_5",
    },
    # ---------------- Mens ----------------
    "m": {
        "XXXXX_1": "COLLECTION_1",
        "XXXXX_2": "COLLECTION_2",
        "XXXXX_3": "COLLECTION_3",
        "XXXXX_4": "COLLECTION_4",
        "XXXXX_5": "COLLECTION_5",
    },
}


# ================================================================
#  GOOGLE SHEET LOADERS (live data, cached 10 min)
# ================================================================
@_cache_data(ttl=600)
def load_price_data():
    """Load currency price ladder from Google Sheet -> {currency: [values]}."""
    try:
        url = (
            "https://docs.google.com/spreadsheets/d/e/"
            "2PACX-1vRdAQmBHwDEWCgmLdEdJc0HsFYpPSyERPHLwmr2tnTYU1BDWdBD6I0ZYfEDzataX0wTNhfLfnm-Te6w/"
            "pub?gid=583402611&single=true&output=csv"
        )
        df = pd.read_csv(url)
        if df.empty:
            return None
        return {currency: df[currency].dropna().tolist() for currency in df.columns}
    except Exception:
        return None


@_cache_data(ttl=600)
def load_product_translations():
    """Load product-name translations (21 languages) from Google Sheet."""
    try:
        sheet_id = "1ue68TSJQQedKa7sVBB4syOc0OXJNaLS7p9vSnV52mKA"
        sheet_name = "SS26 Product_Name"
        encoded = requests.utils.quote(sheet_name)
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={encoded}"
        df = pd.read_csv(url)
        return df
    except Exception:
        return pd.DataFrame()


@_cache_data(ttl=600)
def load_material_translations():
    """Load material translations (AL, MK) with a Cotton-only fallback."""
    try:
        url = (
            "https://docs.google.com/spreadsheets/d/e/"
            "2PACX-1vRdAQmBHwDEWCgmLdEdJc0HsFYpPSyERPHLwmr2tnTYU1BDWdBD6I0ZYfEDzataX0wTNhfLfnm-Te6w/"
            "pub?gid=1096440227&single=true&output=csv"
        )
        df = pd.read_csv(url)
        if df.empty:
            raise ValueError("Empty sheet")

        material_translations = []
        for _, row in df.iterrows():
            name = row.get('Name') if 'Name' in row and pd.notna(row.get('Name')) else (
                row.iloc[0] if len(row) else None
            )
            if not name or pd.isna(name):
                continue
            for lang in ['AL', 'MK']:
                tr = row.get(lang, "")
                tr = "" if pd.isna(tr) else tr
                material_translations.append({'material': name, 'language': lang, 'translation': tr})

        if not material_translations:
            raise ValueError("No material rows produced")
        return pd.DataFrame(material_translations)

    except Exception:
        fallback = [
            {'material': 'Cotton', 'language': 'AL', 'translation': 'Cotton'},
            {'material': 'Cotton', 'language': 'MK', 'translation': 'Cotton'},
        ]
        return pd.DataFrame(fallback)


# ================================================================
#  CLASSIFICATION / DEPARTMENT / COLLECTION HELPERS
# ================================================================
def get_classification_type(item_class):
    """Item_classification text -> COLLECTION_MAPPING key."""
    if not item_class:
        return None
    ic = item_class.lower()
    mapping = [
        ('younger girls outerwear', 'yg'), ('older girls outerwear', 'og'),
        ('younger boys outerwear', 'yb'), ('older boys outerwear', 'ob'),
        ('baby girls outerwear', 'a'), ('baby boys outerwear', 'b'),
        ('baby girls essentials', 'd_girls'), ('baby boys essentials', 'd'),
        ('ladies outerwear', 'l'), ('mens outerwear', 'm'),
    ]
    for needle, key in mapping:
        if needle in ic:
            return key
    return None


def map_item_class_to_dept_label(item_class):
    """Item_classification text -> UI department label."""
    if not item_class:
        return None
    ic = item_class.lower()
    if 'baby boys outerwear' in ic or 'baby boys essentials' in ic:
        return "Baby Boy"
    if 'baby girls outerwear' in ic or 'baby girls essentials' in ic:
        return "Baby Girl"
    if 'younger boys outerwear' in ic or 'older boys outerwear' in ic:
        return "Boys"
    if 'younger girls outerwear' in ic or 'older girls outerwear' in ic:
        return "Girls"
    if 'ladies outerwear' in ic:
        return "Women"
    if 'mens outerwear' in ic:
        return "Mens"
    return None


def get_dept_value(item_class):
    """Item_classification text -> Dept column (BABY/KIDS/TEENS/WOMEN/MEN)."""
    if not item_class:
        return ""
    ic = item_class.lower()
    if any(x in ic for x in ['baby boys', 'baby girls']):
        return "BABY"
    if any(x in ic for x in ['younger boys', 'younger girls']):
        return "KIDS"
    if any(x in ic for x in ['older girls', 'older boys']):
        return "TEENS"
    if 'ladies outerwear' in ic:
        return "WOMEN"
    if 'mens outerwear' in ic:
        return "MEN"
    return ""


def extract_collection_value(raw_text):
    """Format 'TYPE - NAME - SEASON - CODE' -> NAME (skips TYPE/SEASON/CODE)."""
    parts = [p.strip() for p in raw_text.split("-") if p.strip()]
    if not parts:
        return "UNKNOWN"
    parts = parts[1:]  # skip TYPE
    for p in parts:
        if re.fullmatch(r"[A-Za-z]{2}\d{2}", p):  # skip SEASON (SS27, AW26)
            continue
        if p.isdigit():  # skip CODE
            continue
        return p
    return "UNKNOWN"


def modify_collection(collection, item_class):
    """Append ' B' / ' G' to the collection name based on gender group."""
    if not item_class:
        return collection
    ic = item_class.lower()
    if any(x in ic for x in ['younger boys', 'older boys']):
        return f"{collection} B"
    if any(x in ic for x in ['younger girls', 'older girls']):
        return f"{collection} G"
    return collection


def clean_item_name_english(name: str) -> str:
    """Strip a leading 'NN.' index and known prefixes, return UPPERCASE."""
    if not isinstance(name, str):
        return ""
    text = re.sub(r'^\d+\.\s*', '', name.strip()).strip()
    return text.upper()


# ================================================================
#  PRICE LADDER HELPERS
# ================================================================
def format_number(value, currency):
    """Format a price for display, currency-appropriate decimal style."""
    try:
        if isinstance(value, str):
            value = float(value.replace(',', '.'))
        if currency in ['EUR', 'BGN', 'BAM', 'RON', 'PLN']:
            formatted = f"{float(value):,.2f}".replace(".", ",")
            if ',' in formatted:
                parts = formatted.split(',')
                parts[0] = parts[0].replace('.', '')
                formatted = ','.join(parts)
            return formatted
        return str(int(float(value)))
    except (ValueError, TypeError):
        return str(value)


def find_closest_price(pln_value):
    """PLN price -> {currency: formatted_value} using the live price ladder."""
    try:
        price_data = load_price_data()
        if not price_data or 'PLN' not in price_data:
            return None
        pln_value = float(pln_value)
        ladder = price_data['PLN']
        if pln_value not in ladder:
            return None
        idx = ladder.index(pln_value)
        return {
            currency: format_number(values[idx], currency)
            for currency, values in price_data.items() if currency != 'PLN'
        }
    except Exception:
        return None


# ================================================================
#  PDF TEXT-LEVEL EXTRACTION HELPERS
# ================================================================
def detect_pl_sales_price(full_text):
    m = re.search(r"PL\s+[^\n]*?(\d+[\.,]\d+)", full_text)
    return m.group(1).replace(',', '.') if m else None


def extract_sizes_from_pdf(pages_text):
    """Sizes list under a 'Sizes' header, comma-joined (e.g. '9/10, 11/12')."""
    size_pattern = re.compile(
        r"^(?:\d+(?:[/-]\d+)?|[A-Za-z]{1,4}(?:/[A-Za-z]{1,4})?)$", re.IGNORECASE
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


def extract_pl_sales_price_from_pdf(pages_text):
    """PL (Poland) sales price, searched line-by-line for robustness."""
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


def extract_colour_from_pdf_pages(pages_text):
    """Robust colour detection across old/new PEPCO tech-pack layouts.
    Returns "UNKNOWN" if nothing found — caller shows a manual-entry
    fallback (Phase 4 UI), same pattern as extractor.py's other fields.
    """
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
    return "UNKNOWN"


def extract_order_id_only(file):
    """Extract just the Order ID (used when merging multiple PDF uploads)."""
    pos = None
    try:
        pos = file.tell()
    except Exception:
        pass
    try:
        file.seek(0)
    except Exception:
        pass
    try:
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            page1_text = doc[0].get_text() if len(doc) > 0 else ""
    except Exception:
        try:
            file.seek(0 if pos is None else pos)
        except Exception:
            pass
        return None
    try:
        file.seek(0 if pos is None else pos)
    except Exception:
        pass
    m = re.search(r"Order\s*-\s*ID\s*\.{2,}\s*([A-Z0-9_+-]+)", page1_text, re.IGNORECASE)
    return m.group(1).strip() if m else None


# ================================================================
#  MAIN EXTRACTION ENGINE
# ================================================================
def extract_data_from_pdf(file):
    """
    Robust PEPCO Hangtag/Swingtag extractor (5-page + 6-page tech packs).

    Returns (results, pl_price_detected, flags) where:
      - results: list of per-row dicts (one per SKU/barcode/size), each with
        Order_ID, Style, Colour, Supplier_product_code, Item_classification,
        Supplier_name, today_date, Collection, Colour_SKU,
        Style_Merch_Season, Batch, barcode, Item_name_EN, Season, Sizes
      - pl_price_detected: auto-detected PL price string, or None
      - flags: {"collection_manual": bool, "colour_manual": bool} — True
        means the value fell back to "UNKNOWN" and Phase-4 UI should
        prompt the user for manual entry.
    """
    try:
        raw = file.read()
        if not raw:
            return None, None, {}

        doc = fitz.open(stream=raw, filetype="pdf")
        if len(doc) < 1:
            return None, None, {}

        pages_text = [doc[i].get_text() for i in range(len(doc))]
        full_text = "\n".join(pages_text)
        page1 = pages_text[0]

        # ---- Item Name EN ----
        item_name_en = None
        m_item = re.search(r"Item\s*name\s*English\s*[:\.]{1,}\s*(.+)", full_text, re.IGNORECASE)
        if not m_item:
            m_item = re.search(r"Item\s*name\s*[:\.]{1,}\s*(.+?)\n", full_text, re.IGNORECASE)
        if m_item:
            item_name_en = m_item.group(1).strip()

        # ---- Sizes + PL price ----
        sizes = extract_sizes_from_pdf(pages_text)
        pl_price_detected = extract_pl_sales_price_from_pdf(pages_text)

        # ---- Identifiers ----
        merch_code = re.search(r"Merch\s*code\s*\.{2,}\s*([\w/]+)", page1)
        season = re.search(r"Season\s*\.{2,}\s*(\w+)?\s*(\d{2})", page1)
        style_code = re.search(r"\b\d{6}\b", page1)

        style_suffix = ""
        if merch_code and season:
            style_suffix = f"{merch_code.group(1).strip()}{season.group(2)}"
        elif merch_code:
            style_suffix = merch_code.group(1).strip()

        collection = re.search(r"Collection\s*\.{2,}\s*(.+)", page1)
        collection_value = extract_collection_value(collection.group(1)) if collection else "UNKNOWN"
        collection_manual = not collection_value or collection_value == "UNKNOWN"

        date_match = re.search(r"Handover\s*date\s*\.{2,}\s*(\d{2}/\d{2}/\d{4})", page1)
        batch = "UNKNOWN"
        if date_match:
            try:
                batch_date = datetime.strptime(date_match.group(1), "%d/%m/%Y")
                batch = (batch_date - timedelta(days=20)).strftime("%m%Y")
            except Exception:
                pass

        order_id = re.search(r"Order\s*-\s*ID\s*\.{2,}\s*(.+)", page1)
        item_class = re.search(r"Item classification\s*\.{2,}\s*(.+)", page1)
        supplier_code = re.search(r"Supplier product code\s*\.{2,}\s*(.+)", page1)
        supplier_name = re.search(r"Supplier name\s*\.{2,}\s*(.+)", page1)
        item_class_value = item_class.group(1).strip() if item_class else "UNKNOWN"

        # ---- Collection mapping (raw name -> display name) ----
        class_type = get_classification_type(item_class_value)
        if class_type and class_type in COLLECTION_MAPPING:
            for orig, new in COLLECTION_MAPPING[class_type].items():
                if orig.upper() in collection_value.upper():
                    collection_value = new
                    break

        # ---- Colour ----
        colour = extract_colour_from_pdf_pages(pages_text)
        colour_manual = colour == "UNKNOWN"

        # ---- SKU + Barcode ----
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

        if not skus or not valid_barcodes:
            return None, None, {"error": "SKU or Barcode missing."}

        if len(skus) != len(valid_barcodes):
            min_len = min(len(skus), len(valid_barcodes))
            skus = skus[:min_len]
            valid_barcodes = valid_barcodes[:min_len]

        season_value = f"{season.group(1)}{season.group(2)}" if season else "UNKNOWN"

        # ---- Build one row per SKU/barcode/size ----
        results = []
        sizes_list = [s.strip() for s in sizes.split(",")] if sizes else [""]
        colour_disp = colour.title()

        for sku, barcode, size in zip(skus, valid_barcodes, sizes_list):
            results.append({
                "Order_ID": order_id.group(1).strip() if order_id else "UNKNOWN",
                "Style": style_code.group() if style_code else "UNKNOWN",
                "Colour": colour_disp,
                "Supplier_product_code": supplier_code.group(1).strip() if supplier_code else "UNKNOWN",
                "Item_classification": item_class_value,
                "Supplier_name": supplier_name.group(1).strip() if supplier_name else "UNKNOWN",
                "today_date": datetime.today().strftime('%d-%m-%Y'),
                "Collection": collection_value,
                "Colour_SKU": f"{colour} • SKU {sku}",
                "Style_Merch_Season": (
                    f"STYLE {style_code.group()} • {style_suffix} • Batch No./"
                    if style_code else "STYLE UNKNOWN"
                ),
                "Batch": f"виготовлення: {batch}",
                "barcode": barcode,
                "Item_name_EN": item_name_en or "",
                "Season": season_value,
                "Sizes": size,
                "Dept": get_dept_value(item_class_value),
            })

        flags = {"collection_manual": collection_manual, "colour_manual": colour_manual}
        return results, pl_price_detected, flags

    except Exception as e:
        return None, None, {"error": str(e)}


# ================================================================
#  TRANSLATION FORMATTER (21 languages + material composition)
# ================================================================
def format_product_translations(
    product_name,
    translation_row,
    selected_materials=None,
    material_translations=None,
    material_compositions=None,
):
    """Builds the multilingual '|EN| ... |AL| ... |MK| ...' product_name block."""
    formatted = []

    country_suffixes = {
        'BiH': " Sastav materijala na ušivenoj etiketi.",
        'RS': " Sastav materijala nalazi se na ušivenoj etiketi.",
        'UA': (
            " Імпортер приймає претензії. Термін придатності – необмежений, якщо продукт "
            "використовується за призначенням (якщо на упаковці або продукті не вказано "
            "термін придатності). Умови зберігання – Зберігати в сухому місці при "
            "кімнатній температурі."
        ),
    }

    en_text = translation_row.get('EN', product_name)
    formatted.append(f"|EN| {en_text}")

    combined_lang = {
        'ES': (
            f"{translation_row['ES']} / {translation_row['ES_CA']}"
            if pd.notna(translation_row.get('ES_CA')) else translation_row.get('ES')
        )
    }

    language_order = [
        'AL', 'BG', 'BiH', 'CZ', 'DE', 'EE', 'ES', 'GR', 'HR', 'HU', 'IT',
        'LT', 'LV', 'MK', 'PL', 'PT', 'RO', 'RS', 'SI', 'SK', 'UA',
    ]

    for lang in language_order:
        text = combined_lang.get(lang) if lang in combined_lang and combined_lang[lang] is not None \
            else translation_row.get(lang, product_name)

        if selected_materials and material_translations and lang in ['AL', 'MK']:
            comp = (material_compositions or {}).get(lang, "")
            names = material_translations.get(lang, "")
            if comp:
                text = f"{text}: {comp}"
            elif names:
                text = f"{text}: {names}"

        if lang in country_suffixes:
            if not text.endswith('.'):
                text += "."
            text += country_suffixes[lang]

        formatted.append(f"|{lang}| {text}")

    return " ".join(formatted)
