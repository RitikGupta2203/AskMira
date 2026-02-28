import streamlit as st

def show_info():
    st.markdown(
        """
        <div style="text-align:center;">
          <div style="
            font-family:'Cinzel Decorative', serif;
            font-size:4rem;
            color:#2E86AB;
          ">
            AskMira
          </div>
          <div style="
            font-family:'Cinzel Decorative', serif;
            font-size:2.5rem;
            color:#2E86AB;
            margin-top:-0.5rem;
          ">
          </div>
          <p style="font-size:1.2rem; color:#555;">
            Your AI assistant for credit evaluations…
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
