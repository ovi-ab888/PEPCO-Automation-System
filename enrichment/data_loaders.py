# ================================================================
#  swingtag_csv/data_loaders.py
#  Google Sheet theke data load korar function.
#  NOTE: load_material_translations() ei port-e rakha hoyni — SS27
#  app.py ota import-i kore na (composition_care.py-r nijer
#  load_care_composition_data() diye material data ashe).
# ================================================================
import pandas as pd
import requests
import streamlit as st


@st.cache_data(ttl=600)
def load_price_data():
    """Load currency price ladder from Google Sheet."""
    try:
        url = (
            "https://docs.google.com/spreadsheets/d/e/"
            "2PACX-1vRdAQmBHwDEWCgmLdEdJc0HsFYpPSyERPHLwmr2tnTYU1BDWdBD6I0ZYfEDzataX0wTNhfLfnm-Te6w/"
            "pub?gid=583402611&single=true&output=csv"
        )
        df = pd.read_csv(url)
        if df.empty:
            st.error("Price data sheet is empty")
            return None
        return {currency: df[currency].dropna().tolist() for currency in df.columns}
    except Exception as e:
        st.error(f"Failed to load price data: {str(e)}")
        return None


@st.cache_data(ttl=600)
def load_product_translations():
    """Load product name translations from Google Sheet."""
    try:
        sheet_id = "1ue68TSJQQedKa7sVBB4syOc0OXJNaLS7p9vSnV52mKA"
        sheet_name = "SS26 Product_Name"
        encoded = requests.utils.quote(sheet_name)
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={encoded}"
        df = pd.read_csv(url)
        if df.empty:
            st.error("Loaded translations but sheet appears empty")
        return df
    except Exception as e:
        st.error(f"❌ Failed to load translations: {str(e)}")
        return pd.DataFrame()
