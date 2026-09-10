import streamlit as st


def render_footer():
    """
    Renders the app footer. Styling lives in components/theme.py.
    """
    st.markdown("""
        <div class="al-footer">
            © 2026 AuraLedgerIQ. All rights reserved.
        </div>
    """, unsafe_allow_html=True)
