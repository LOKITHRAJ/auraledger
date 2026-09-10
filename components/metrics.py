import streamlit as st


def render_kpi_card(title: str, value: str, icon: str, color: str = "#1F4E79"):
    """
    Renders one KPI card. Styling lives in components/theme.py (injected once
    in app.py) -- previously this injected a full <style> block on every call
    (4-6 times per Dashboard render).
    """
    st.markdown(f"""
        <div class="al-kpi">
            <div class="al-kpi-icon" style="color:{color};">{icon}</div>
            <div>
                <p class="al-kpi-title">{title}</p>
                <p class="al-kpi-value">{value}</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
