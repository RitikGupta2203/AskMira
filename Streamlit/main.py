import os
import sys
import streamlit as st
import requests
from dotenv import load_dotenv

# ─── Project Root ──────────────────────────────────────────────────────────────
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ─── Load Environment ─────────────────────────────────────────────────────────
load_dotenv()
FASTAPI_URL  = os.getenv("FASTAPI_URL", "http://127.0.0.1:8000")
REGISTER_URL = f"{FASTAPI_URL}/auth/register"
LOGIN_URL    = f"{FASTAPI_URL}/auth/login"

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="AskMira Auth", layout="centered")

# ─── SESSION STATE ────────────────────────────────────────────────────────────
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("access_token", None)
st.session_state.setdefault("auth_username", None)

# ─── INJECT ARTISTIC FONT + STYLES ─────────────────────────────────────────────
st.markdown(
    """
    <link href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&display=swap" rel="stylesheet">
    <style>
      body { background: #f5f7fa; }
      .header {
        font-family: 'Cinzel Decorative', serif;
        font-size: 3.5rem;
        color: #2E86AB;
        text-align: center;
        margin-bottom: 1rem;
      }
      .stTextInput>div>div>input { border-radius: 0.5rem; }
      .stSelectbox>div>div       { border-radius: 0.5rem; }
      .stButton>button {
        background-color: #2E86AB;
        color: white;
        border-radius: 0.5rem;
        padding: 0.8rem 0;
        font-size: 1.2rem;
        width: 100%;
      }
      .stButton>button:hover {
        background-color: #1B4F72;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── AUTH HELPERS ──────────────────────────────────────────────────────────────
def signup(username: str, email: str, password: str):
    r = requests.post(REGISTER_URL, json={
        "username": username,
        "email": email,
        "password": password
    })
    if r.status_code in (200, 201):
        st.success("✅ Account created! Please log in.")
        return
    try:
        detail = r.json().get("detail", r.text)
    except ValueError:
        detail = r.text or "Unknown error"
    st.error(f"Signup failed [{r.status_code}]: {detail}")

def login(username: str, password: str):
    r = requests.post(LOGIN_URL, json={
        "username": username,
        "password": password
    })
    if r.status_code == 200:
        try:
            token = r.json().get("access_token")
        except ValueError:
            st.error("Login failed: invalid JSON")
            return
        if token:
            st.session_state["access_token"]  = token
            st.session_state["logged_in"]     = True
            st.session_state["auth_username"] = username
            st.rerun()
        else:
            st.error("Login failed: no token returned")
        return
    try:
        detail = r.json().get("detail", r.text)
    except ValueError:
        detail = r.text or "Unknown error"
    st.error(f"Login failed [{r.status_code}]: {detail}")

# ─── AUTH PAGE ─────────────────────────────────────────────────────────────────
def auth_page():
    st.markdown('<div class="header">AskMira</div>', unsafe_allow_html=True)

    mode = st.selectbox("", ["Login", "Signup"], key="auth_mode")
    username = st.text_input("Username", key="auth_username_input")
    password = st.text_input("Password", type="password", key="auth_password_input")
    email = st.text_input("Email", key="auth_email_input") if mode == "Signup" else None

    if st.button(mode):
        if mode == "Signup":
            if username and email and password:
                signup(username, email, password)
            else:
                st.error("Fill in all fields to sign up.")
        else:
            if username and password:
                login(username, password)
            else:
                st.error("Enter both username and password.")

# ─── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    if not st.session_state["logged_in"]:
        auth_page()
    else:
        st.sidebar.markdown(f"👤 **{st.session_state['auth_username']}**")
        if st.sidebar.button("Logout"):
            st.session_state["logged_in"]     = False
            st.session_state["access_token"]  = None
            st.session_state["auth_username"] = None
            st.rerun()

        # when logged in, hand off to landing
        import landing
        landing.run()

if __name__ == "__main__":
    main()
