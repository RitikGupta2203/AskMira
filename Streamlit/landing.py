import streamlit as st
import informationpage
import AskMirabot
import AACROEDGE

# map each page name to its handler function
PAGES = {
    "Welcome":       {"module": informationpage, "func": "show_info"},
    "AskMira Bot":   {"module": AskMirabot,    "func": "show_bot"},
    "AACRAO EDGE":   {"module": AACROEDGE,     "func": "show_edge"},
}

def run():
    st.sidebar.title("Navigation")
    for name in PAGES:
        if st.sidebar.button(name):
            st.session_state.current_page = name

    if "current_page" not in st.session_state:
        st.session_state.current_page = "Welcome"

    page_info = PAGES[st.session_state.current_page]
    fn = getattr(page_info["module"], page_info["func"])
    fn()

if __name__ == "__main__":
    run()
