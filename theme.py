"""
theme.py
Loads static/css/style.css (same design system as plate_planner_app) so
this app matches it visually — dark/light mode, Inter font, card layout.
Also handles the PEPCO logo (logo.svg, repo root) shown on the login page
and the main app header.
"""
import os
import base64
import streamlit as st

CSS_PATH = os.path.join(os.path.dirname(__file__), "static", "css", "style.css")
LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo.svg")


def load_css():
    with open(CSS_PATH, "r") as f:
        css = f.read()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _logo_data_uri() -> str | None:
    """Base64-embeds logo.svg so it renders reliably everywhere (Streamlit's
    st.image has spotty SVG support across versions) — returns None if the
    file isn't there yet, so callers can skip it gracefully."""
    if not os.path.exists(LOGO_PATH):
        return None
    with open(LOGO_PATH, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    return f"data:image/svg+xml;base64,{encoded}"


def main_header(title: str, subtitle: str = ""):
    """Matches the .main-header / .card-title classes from style.css.
    Shows the PEPCO logo above the title if logo.svg exists at repo root."""
    logo_uri = _logo_data_uri()
    logo_html = f'<img src="{logo_uri}" style="height:56px; margin-bottom:10px;" />' if logo_uri else ""
    st.markdown(
        f"""
        <div class="main-header">
            {logo_html}
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
