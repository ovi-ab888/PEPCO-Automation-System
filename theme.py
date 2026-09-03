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


def render_badge(text: str, muted: bool = False) -> None:
    """Small indigo pill badge, e.g. next to a selected variant name or a
    'Coming soon' tag on an unfinished section.

    Usage:
        theme.render_badge("KVI Size Sticker")
        theme.render_badge("Coming soon", muted=True)
    """
    cls = "pepco-badge muted" if muted else "pepco-badge"
    st.markdown(f'<span class="{cls}">{text}</span>', unsafe_allow_html=True)


def render_steps(current_step: int, total_steps: int = 3) -> None:
    """Top-right 1-2-3 circle step indicator (compact version).

    Usage (top of each stage in app.py):
        theme.render_steps(1)   # Upload
        theme.render_steps(2)   # Review & correct
        theme.render_steps(3)   # Select labels & generate
    """
    circles = ""
    for i in range(1, total_steps + 1):
        active_cls = " active" if i == current_step else ""
        circles += f'<span class="pepco-step-circle{active_cls}">{i}</span>'
    st.markdown(f'<div class="pepco-steps">{circles}</div>', unsafe_allow_html=True)


def render_progress_tabs(current_step: int, labels: list[str]) -> None:
    """Wide labeled pill-tab progress bar (kept for optional single use at
    the very top of the page). For inline per-section markers, use
    render_stage_line() instead — it's much lighter.

    Usage:
        theme.render_progress_tabs(1, ["Upload / Extract", "Review", "Select & generate"])
    """
    tabs_html = ""
    for i, label in enumerate(labels, start=1):
        active_cls = " active" if i == current_step else ""
        tabs_html += f'<div class="pepco-tab{active_cls}">{i}. {label}</div>'
    st.markdown(f'<div class="pepco-tabs">{tabs_html}</div>', unsafe_allow_html=True)


def render_stage_line(current_step: int, labels: list[str]) -> None:
    """Compact one-line stage marker — small dots + the current stage's
    label, instead of a full tab bar. Meant to repeat cheaply at the top
    of every section without feeling heavy.

    Usage:
        theme.render_stage_line(2, ["Upload / Extract", "Review", "Select & generate"])
        -> ● ─ ● ─ ○   Step 2 of 3 — Review
    """
    total = len(labels)
    dots = ""
    for i in range(1, total + 1):
        state = "done" if i < current_step else ("current" if i == current_step else "")
        dots += f'<span class="pepco-dot {state}"></span>'
        if i < total:
            line_state = "done" if i < current_step else ""
            dots += f'<span class="pepco-dot-line {line_state}"></span>'
    label = labels[current_step - 1]
    st.markdown(
        f'<div class="pepco-stage-line">'
        f'<span class="pepco-dots">{dots}</span>'
        f'<span class="pepco-stage-text">Step {current_step} of {total} — {label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_stage_banner(current_step: int, labels: list[str]) -> None:
    """Big centered banner showing just the current stage — e.g. a wide
    bordered box reading "2. Review". One call per section in app.py.

    Usage:
        theme.render_stage_banner(2, ["Upload / Extract", "Review", "Select & generate"])
    """
    label = labels[current_step - 1]
    st.markdown(
        f'<div class="pepco-stage-banner">{current_step}. {label}</div>',
        unsafe_allow_html=True,
    )


def render_section_row(label: str, badge_text: str = None, muted_badge: bool = False) -> None:
    """Inline label + optional badge, for use just inside an st.expander
    body (Streamlit expander titles are plain text only, so this renders
    as the first line of the expander's content instead).

    Usage:
        with st.expander("Size Tag"):
            theme.render_section_row("Size Tag", "Regular · PB and PG")
    """
    badge_html = ""
    if badge_text:
        cls = "pepco-badge muted" if muted_badge else "pepco-badge"
        badge_html = f'<span class="{cls}">{badge_text}</span>'
    st.markdown(
        f'<div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">'
        f'<span style="font-size:13px;">{label}</span>{badge_html}</div>',
        unsafe_allow_html=True,
    )
