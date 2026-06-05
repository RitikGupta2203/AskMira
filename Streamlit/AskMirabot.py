import streamlit as st
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://fastapi:8000")
CHAT_URL = f"{FASTAPI_URL}/rag/chat"


def _force_logout(msg: str):
    st.session_state["logged_in"] = False
    st.session_state["access_token"] = None
    st.session_state["auth_username"] = None
    st.warning(msg)
    st.rerun()


def get_rag_response(query: str) -> str:
    """Send the question + JWT to FastAPI's /rag/chat. FastAPI does the RAG work."""
    token = st.session_state.get("access_token")
    if not token:
        _force_logout("Please log in.")
        return ""
    try:
        st.write("🔍 Searching knowledge base...")
        r = requests.post(
            CHAT_URL,
            json={"query": query},
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        if r.status_code == 401:
            _force_logout("Your session expired — please log in again.")
            return ""
        r.raise_for_status()
        return r.json().get("response", "")
    except requests.RequestException as e:
        return f"⚠️ Error reaching the RAG service: {e}"
    except Exception as e:
        return f"⚠️ Error generating response: {e}"

def show_bot():
    # Decorative header
    st.markdown(
        """
        <div style="text-align:center;">
          <div style="
            font-family:'Cinzel Decorative', serif;
            font-size:3rem;
            color:#2E86AB;
          ">
            AskMira Bot
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    # Prompt
    user_input = st.chat_input("Type your question here…")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.chat_message("user").write(user_input)

        with st.chat_message("assistant"):
            resp = get_rag_response(user_input)
            st.write(resp)
            st.session_state.messages.append({"role": "assistant", "content": resp})