import streamlit as st
from services.authentication import login
from config.config_manager import ConfigManager
from config import settings
from components.theme import COLORS

def show_login():
    """
    Renders either the First-Run Setup Wizard or the centered login card.
    """
    config_mgr = ConfigManager()
    saved_key = config_mgr.get_api_key()

    # ai_client.py already prefers settings.GEMINI_API_KEY/OPENAI_API_KEY (.env
    # locally, st.secrets on Streamlit Cloud) over this local encrypted-storage
    # key, falling back to the latter only when neither is set. The wizard
    # should follow the same precedence -- otherwise a Cloud deploy with the
    # key already in Secrets still forces every visitor through local setup,
    # which then tries to persist to the container's shared, ephemeral disk.
    env_key_present = bool(settings.GEMINI_API_KEY or settings.OPENAI_API_KEY)

    # Force setup only if no API key is available from either source
    is_first_run = not saved_key and not env_key_present

    st.markdown(f"""
        <style>
        /* Clean, light backdrop -- consistent with the rest of the app's theme
        (components/theme.py) rather than a one-off dark gradient. Scoped to this
        screen only: re-injected fresh each render, and never applies once the
        user is authenticated and Login.py stops being called. */
        .stApp {{
            background: linear-gradient(160deg, #FFFFFF 0%, {COLORS["bg"]} 100%) !important;
        }}
        .main .block-container {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            min-height: 92vh;
            padding-top: 0;
            padding-bottom: 0;
        }}

        @keyframes al-login-rise {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* The actual card: a real st.container(border=True) below, not a
        manually-inserted <div> -- that's what guarantees the input fields and
        their labels render INSIDE this white box (and therefore stay legible)
        rather than on the page background behind it. */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            animation: al-login-rise 0.35s ease-out;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] > div {{
            background: {COLORS["card_bg"]};
            border-radius: 16px;
            padding: 8px 12px;
        }}

        .login-avatar {{
            width: 52px;
            height: 52px;
            margin: 4px auto 14px auto;
            border-radius: 14px;
            background: linear-gradient(135deg, {COLORS["primary"]} 0%, {COLORS["primary_dark"]} 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
        }}

        .login-logo {{
            text-align: center;
            font-size: 24px;
            font-weight: 700;
            color: {COLORS["primary_dark"]};
            margin-bottom: 4px;
            letter-spacing: -0.3px;
        }}

        .login-subtitle {{
            text-align: center;
            font-size: 14px;
            color: {COLORS["text_muted"]};
            margin-bottom: 4px;
        }}

        [data-testid="stTextInput"] input {{
            padding: 10px 14px !important;
        }}
        [data-testid="stTextInput"] input:focus {{
            box-shadow: 0 0 0 3px rgba(31, 78, 121, 0.15) !important;
            border-color: {COLORS["primary"]} !important;
        }}

        .setup-header {{
            font-size: 18px;
            font-weight: 700;
            color: {COLORS["primary_dark"]};
            margin-bottom: 10px;
            border-bottom: 2px solid {COLORS["border"]};
            padding-bottom: 8px;
        }}

        .login-tagline {{
            text-align: center;
            color: {COLORS["text_muted"]};
            font-size: 12px;
            margin-top: 24px;
            letter-spacing: 0.5px;
        }}
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        if is_first_run:
            with st.container(border=True):
                st.markdown('<div class="login-avatar">✨</div>', unsafe_allow_html=True)
                st.markdown('<div class="login-logo">AuraLedgerIQ Setup</div>', unsafe_allow_html=True)
                st.markdown('<div class="login-subtitle">Desktop First-Run Configuration Wizard</div>', unsafe_allow_html=True)

                if "setup_step" not in st.session_state:
                    st.session_state["setup_step"] = 1

                step = st.session_state["setup_step"]

                st.write("")

                if step == 1:
                    st.markdown('<div class="setup-header">Step 1: Welcome to AuraLedgerIQ</div>', unsafe_allow_html=True)
                    st.write("Let's connect your AI provider. Your statement data stays on this machine.")
                    st.write("")
                    if st.button("Continue ➡️", type="primary", use_container_width=True):
                        st.session_state["setup_step"] = 2
                        st.rerun()

                elif step == 2:
                    st.markdown('<div class="setup-header">Step 2: Select AI Provider</div>', unsafe_allow_html=True)
                    provider = st.radio(
                        "Choose preferred AI model provider:",
                        ["Gemini", "OpenAI"],
                        help="Select the AI Client interface to run classification."
                    )
                    st.session_state["setup_provider"] = provider
                    st.write("")
                    col_back, col_next = st.columns(2)
                    if col_back.button("⬅️ Back", use_container_width=True):
                        st.session_state["setup_step"] = 1
                        st.rerun()
                    if col_next.button("Next ➡️", type="primary", use_container_width=True):
                        st.session_state["setup_step"] = 3
                        st.rerun()

                elif step == 3:
                    st.markdown('<div class="setup-header">Step 3: Enter API Key</div>', unsafe_allow_html=True)
                    provider = st.session_state.get("setup_provider", "Gemini")
                    st.write(f"Configure authorization credentials for **{provider}** model execution.")

                    key_input = st.text_input(
                        f"{provider} API Key",
                        type="password",
                        placeholder=f"Enter {provider} Secret Key..."
                    )

                    st.write("")
                    col_back, col_next = st.columns(2)
                    if col_back.button("⬅️ Back", use_container_width=True):
                        st.session_state["setup_step"] = 2
                        st.rerun()
                    if col_next.button("Next ➡️", type="primary", use_container_width=True):
                        if not key_input:
                            st.error("API Key cannot be blank.")
                        else:
                            st.session_state["setup_key"] = key_input
                            st.session_state["setup_step"] = 4
                            st.rerun()

                elif step == 4:
                    st.markdown('<div class="setup-header">Step 4: Complete Setup</div>', unsafe_allow_html=True)
                    provider = st.session_state.get("setup_provider", "Gemini")
                    st.write("Setup configuration is complete! The API key will be encrypted using Windows DPAPI credentials.")
                    st.write("Click below to finalize setup and open the AuraLedgerIQ login screen.")
                    st.write("")
                    col_back, col_finish = st.columns(2)
                    if col_back.button("⬅️ Back", use_container_width=True):
                        st.session_state["setup_step"] = 3
                        st.rerun()
                    if col_finish.button("🚀 Save & Finish", type="primary", use_container_width=True):
                        # Save configuration to AppData
                        config = config_mgr.load_config()
                        config["ai_provider"] = provider
                        config_mgr.save_config(config)
                        config_mgr.set_api_key(st.session_state["setup_key"])
                        st.session_state["setup_step"] = 1
                        st.rerun()

        else:
            with st.container(border=True):
                st.markdown('<div class="login-avatar">✨</div>', unsafe_allow_html=True)
                st.markdown('<div class="login-logo">AuraLedgerIQ</div>', unsafe_allow_html=True)
                st.markdown('<div class="login-subtitle">Your intelligent financial transaction ledger</div>', unsafe_allow_html=True)

                st.write("")
                username = st.text_input("Username / Email", placeholder="e.g. admin", label_visibility="visible")
                password = st.text_input("Password", type="password", placeholder="••••••••", label_visibility="visible")

                st.write("")

                if st.button("Sign In", type="primary", use_container_width=True):
                    if login(username, password):
                        st.session_state["authenticated"] = True
                        st.session_state["current_page"] = "Dashboard"
                        # Straight to rerun -- no success message first. A message that
                        # renders for one frame before an immediate rerun just adds an
                        # extra visual flash without adding real information.
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

        st.markdown('<p class="login-tagline">Secure • Simple • Intelligent</p>', unsafe_allow_html=True)
