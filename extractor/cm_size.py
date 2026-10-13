# ================================================================
#  extractor/cm_size.py
#  PDF-er Sizes column (3/4, 9-12, XL etc) -> cm size mapping.
#  Shob table-er size-string mile prottekta unique (kono conflict nai),
#  tai Dept ba garment-type na dekhei shorashori lookup kora jay.
#  (Ported as-is from PEPCO_Data_Extractor/cm_size.py)
# ================================================================

CM_SIZE_MAPPING = {
    # ---- Baby / Baby Basic ----
    "0-0": "56 cm", "0-3": "62 cm", "3-6": "68 cm", "6-9": "74 cm",
    "9-12": "80 cm", "12-18": "86 cm", "18-24": "92 cm", "24-36": "98 cm",

    # ---- Pre Girl/Boy (general) ----
    "3/4": "104 cm", "4/5": "110 cm", "5/6": "116 cm", "6/7": "122 cm",
    "7/8": "128 cm", "8/9": "134 cm",

    # ---- Older Girl/Boy: Jacket/Dress/Skirt/Trousers/Shorts ----
    "9": "134 cm", "10": "140 cm", "11": "146 cm", "12": "152 cm",
    "13": "158 cm", "14": "164 cm", "15": "170 cm",

    # ---- Older Girl/Boy: T-Shirt/Top/Sweatshirt ----
    "9/10": "134/140 cm", "11/12": "146/152 cm", "13/14": "158/164 cm",

    # ---- Pre Girl/Boy Nightwear & Underwear ----
    "2-3": "92-98 cm", "3-4": "98-104 cm", "5-6": "110-116 cm", "7-8": "122-128 cm",

    # ---- Older Girl/Boy Nightwear ----
    "9-10": "134-140 cm", "11-12": "146-152 cm", "13-14": "158-164 cm", "15+": "170-176 cm",

    # ---- Man / Woman: letter size, passthrough ----
    "XS": "XS", "S": "S", "M": "M", "L": "L", "XL": "XL", "XXL": "XXL", "3XL": "3XL",
}


def get_cm_size(size):
    """Size string -> cm value. Na mile khali ("")."""
    if not size:
        return ""
    size = size.strip()
    return CM_SIZE_MAPPING.get(size, "") or CM_SIZE_MAPPING.get(size.upper(), "")
