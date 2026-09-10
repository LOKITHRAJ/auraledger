import streamlit as st

# Design tokens. Consolidates the slate-navy palette already used throughout the
# app into one place instead of every component re-declaring its own colors.
COLORS = {
    "primary": "#1F4E79",
    "primary_dark": "#1A365D",
    "success": "#38A169",
    "danger": "#E53E3E",
    "warning": "#DD6B20",
    "bg": "#F7FAFC",
    "card_bg": "#FFFFFF",
    "border": "#E2E8F0",
    "text": "#2D3748",
    "text_muted": "#718096",
}

_INJECTED_KEY = "_theme_injected"


def inject_theme():
    """
    Injects the shared stylesheet once per session. Call this exactly once, from
    app.py, after `st.set_page_config()`. Individual components should reference
    these classes (`.al-card`, `.al-kpi`, etc.) rather than injecting their own
    <style> blocks -- previously every component (header, sidebar, KPI cards)
    re-injected a full stylesheet on every single render.
    """
    if st.session_state.get(_INJECTED_KEY):
        return
    st.session_state[_INJECTED_KEY] = True

    st.markdown(
        f"""
        <style>
        :root {{
            --al-primary: {COLORS["primary"]};
            --al-primary-dark: {COLORS["primary_dark"]};
            --al-success: {COLORS["success"]};
            --al-danger: {COLORS["danger"]};
            --al-warning: {COLORS["warning"]};
            --al-bg: {COLORS["bg"]};
            --al-card-bg: {COLORS["card_bg"]};
            --al-border: {COLORS["border"]};
            --al-text: {COLORS["text"]};
            --al-text-muted: {COLORS["text_muted"]};
        }}

        /* Native Streamlit widget polish */
        .stButton>button {{
            border-radius: 8px !important;
            font-weight: 600 !important;
        }}
        .stTextInput>div>div>input {{
            border-radius: 8px !important;
        }}
        .stFileUploader>div {{
            border-radius: 12px !important;
        }}
        div[data-testid="stMetricValue"] {{
            font-size: 24px !important;
            font-weight: 700 !important;
        }}

        /* Shared card shell used by header, KPI cards, chart panels */
        .al-card {{
            background: var(--al-card-bg);
            border: 1px solid var(--al-border);
            border-radius: 12px;
            padding: 18px 20px;
        }}

        /* Page header */
        .al-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 6px 0 18px 0;
            border-bottom: 1px solid var(--al-border);
            margin-bottom: 20px;
        }}
        .al-header-title {{
            font-size: 28px;
            font-weight: 700;
            color: var(--al-primary-dark);
            margin: 0;
        }}
        .al-header-subtitle {{
            font-size: 14px;
            color: var(--al-text-muted);
            margin: 4px 0 0 0;
        }}
        .al-header-date {{
            font-size: 13px;
            font-weight: 600;
            color: var(--al-text);
            background-color: var(--al-bg);
            padding: 7px 14px;
            border-radius: 20px;
            border: 1px solid var(--al-border);
            white-space: nowrap;
        }}

        /* KPI cards */
        .al-kpi {{
            background: var(--al-card-bg);
            border: 1px solid var(--al-border);
            border-radius: 12px;
            padding: 18px;
            display: flex;
            align-items: center;
            gap: 14px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
        }}
        .al-kpi-icon {{
            font-size: 22px;
            background-color: var(--al-bg);
            padding: 10px;
            border-radius: 10px;
            line-height: 1;
        }}
        .al-kpi-title {{
            font-size: 12px;
            font-weight: 600;
            color: var(--al-text-muted);
            text-transform: uppercase;
            letter-spacing: 0.4px;
            margin: 0;
        }}
        .al-kpi-value {{
            font-size: 22px;
            font-weight: 700;
            color: var(--al-primary-dark);
            margin: 2px 0 0 0;
        }}

        /* Sidebar */
        [data-testid="sidebar-nav"] {{ display: none !important; }}
        .al-sidebar-logo {{
            display: flex;
            align-items: center;
            gap: 10px;
            text-align: left;
            font-size: 20px;
            font-weight: 700;
            color: var(--al-primary-dark);
            padding: 8px 0 16px 0;
            border-bottom: 1px solid var(--al-border);
            margin-bottom: 16px;
        }}
        .al-sidebar-logo-icon {{
            width: 32px;
            height: 32px;
            min-width: 32px;
            border-radius: 9px;
            background: linear-gradient(135deg, var(--al-primary) 0%, var(--al-primary-dark) 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
        }}
        .al-sidebar-profile {{
            background-color: var(--al-bg);
            padding: 12px;
            border-radius: 10px;
            text-align: center;
            margin-top: 30px;
            border: 1px solid var(--al-border);
        }}
        .al-sidebar-profile-name {{
            font-weight: 600;
            color: var(--al-text);
            font-size: 13px;
        }}
        .al-sidebar-profile-role {{
            color: var(--al-text-muted);
            font-size: 11px;
        }}

        /* Empty-state hero (Dashboard / Results) */
        .al-hero {{
            text-align: center;
            padding: 48px 24px;
            background: var(--al-card-bg);
            border: 1px solid var(--al-border);
            border-radius: 16px;
        }}
        .al-hero-title {{
            font-size: 22px;
            font-weight: 700;
            color: var(--al-primary-dark);
            margin: 12px 0 6px 0;
        }}
        .al-hero-subtitle {{
            font-size: 14px;
            color: var(--al-text-muted);
            max-width: 480px;
            margin: 0 auto 20px auto;
        }}

        /* Footer */
        .al-footer {{
            text-align: center;
            padding: 20px 0;
            border-top: 1px solid var(--al-border);
            margin-top: 50px;
            color: var(--al-text-muted);
            font-size: 12px;
        }}

        /* Review-needed banner (Results) */
        .al-review-banner {{
            background: #FFFAF0;
            border: 1px solid #FBD38D;
            border-radius: 12px;
            padding: 14px 18px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}
        .al-review-banner-text {{
            font-weight: 600;
            color: #7B341E;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
