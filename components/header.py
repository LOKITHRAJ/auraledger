import streamlit as st
import datetime


def render_header(title: str, subtitle: str = ""):
    """
    Renders the page header. Styling lives in components/theme.py (injected
    once in app.py) -- this only renders markup.
    """
    now = datetime.datetime.now().strftime("%B %d, %Y")

    st.markdown(f"""
        <div class="al-header">
            <div>
                <h1 class="al-header-title">{title}</h1>
                <p class="al-header-subtitle">{subtitle}</p>
            </div>
            <div class="al-header-date">📅 {now}</div>
        </div>
    """, unsafe_allow_html=True)
