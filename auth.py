"""
auth.py
Simple username/password login gate for the app.

Credentials live in Streamlit secrets (NOT in code, NOT in git) — set them
in Streamlit Cloud under: Manage app -> Settings -> Secrets, like:

    [credentials]
    ovi = "your-password-here"
    staff = "another-password"

    [display_names]
    ovi = "Mr. Ovi"
    staff = "Ms. Staff"

Each key under [credentials] is a valid username; its value is that user's
password. [display_names] is optional — it's the name that gets printed on
the label's "Designer" field. If a username has no entry there, the
username itself (title-cased) is used instead.

For local testing, create a file .streamlit/secrets.toml with the same
content (this file should be in .gitignore, never committed).
"""
import streamlit as st


def check_login() -> bool:
    """
    Shows a login form if the user isn't authenticated yet. Returns True once
    logged in (and lets the rest of the app render); returns False and stops
    the script otherwise — call this at the very top of app.py:

        if not auth.check_login():
            st.stop()
    """
    if st.session_state.get("authenticated"):
        return True

    import theme
    theme.main_header("🔒 PEPCO Label Automation", "Please log in to continue.")

    # centered, card-styled form — narrower than the full page width
    left, center, right = st.columns([1, 1.3, 1])
    with center:
        with st.container(border=True):
            st.markdown(
                '<div class="card-title" style="text-align:center; display:block; '
                'border-bottom:none; margin-bottom:1rem;">Sign in</div>',
                unsafe_allow_html=True,
            )
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                st.write("")
                submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)

    if submitted:
        credentials = st.secrets.get("credentials", {})
        if not credentials:
            st.error("No credentials configured yet — add [credentials] to Streamlit secrets.")
            return False
        if username in credentials and credentials[username] == password:
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            st.rerun()
        else:
            st.error("Wrong username or password.")

    return False


def get_display_name() -> str:
    """The name to print on the label's Designer field for the logged-in
    user — from Streamlit secrets [display_names], falling back to the
    username itself (title-cased) if no mapping is set."""
    username = st.session_state.get("username", "")
    display_names = st.secrets.get("display_names", {})
    return display_names.get(username, username.title())


def logout_button():
    """Optional: call this from the sidebar to let the user log out."""
    if st.session_state.get("authenticated"):
        with st.sidebar:
            st.caption(f"Logged in as **{get_display_name()}**")
            if st.button("Log out"):
                st.session_state["authenticated"] = False
                st.session_state.pop("username", None)
                st.rerun()
