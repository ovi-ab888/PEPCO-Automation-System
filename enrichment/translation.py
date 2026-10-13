# ================================================================
#  swingtag_csv/translation.py
#  Multi-language product name (AL, ES, MK, etc) banano.
#  (Ported as-is from SS27 translation.py — import path adjusted.)
# ================================================================
import pandas as pd

from enrichment.composition_care import build_language_composition


def format_product_translations(product_name, translation_row, composition_ctx=None):
    """Builds multilingual product description with material info."""
    formatted = []

    country_suffixes = {
        'BiH': " Sastav materijala na ušivenoj etiketi.",
        'RS': " Sastav materijala nalazi se na ušivenoj etiketi.",
        'UA': " Імпортер приймає претензії. Термін придатності – необмежений, якщо продукт використовується за призначенням (якщо на упаковці або продукті не вказано термін придатності). Умови зберігання – Зберігати в сухому місці при кімнатній температурі.",
    }

    en_text = translation_row.get('EN', product_name)
    formatted.append(f"|EN| {en_text}")

    combined_lang = {
        'ES': (
            f"{translation_row['ES']} / {translation_row['ES_CA']}"
            if pd.notna(translation_row.get('ES_CA'))
            else translation_row.get('ES')
        )
    }

    language_order = [
        'AL', 'BG', 'BiH', 'CZ', 'DE', 'EE',
        'ES', 'GR', 'HR', 'HU', 'IT', 'LT',
        'LV', 'MK', 'PL', 'PT', 'RO', 'RS',
        'SI', 'SK', 'UA'
    ]

    components_data = composition_ctx["components_data"] if composition_ctx else []

    for lang in language_order:
        if lang in combined_lang and combined_lang[lang] is not None:
            text = combined_lang[lang]
        else:
            text = translation_row.get(lang, product_name)

        if components_data and lang in ['AL', 'MK']:
            comp_text = build_language_composition(
                components_data,
                composition_ctx["materials_df"],
                composition_ctx["comp_translations_df"],
                lang,
                composition_ctx["use_advanced_mode"],
            )
            if comp_text:
                text = f"{text}: {comp_text}"

        if lang in country_suffixes:
            if not text.endswith('.'):
                text += "."
            text += country_suffixes[lang]

        formatted.append(f"|{lang}| {text}")

    return " ".join(formatted)
