import streamlit as st
from components.header import render_header
from components.footer import render_footer
from config.config_manager import ConfigManager
from services.authentication import change_password

def show_settings():
    """
    Renders app configuration settings connected to the local ConfigManager.
    """
    render_header("⚙️ System Settings", "Manage batch processing defaults, AI providers, and custom thresholds.")

    config_mgr = ConfigManager()
    config = config_mgr.load_config()

    st.write("### 🤖 Artificial Intelligence Provider Configurations")
    
    # Provider Settings
    current_provider = config.get("ai_provider", "Gemini")
    provider_options = ["Gemini", "OpenAI"]  # only these two are actually implemented in src/ai_client.py
    try:
        p_idx = provider_options.index(current_provider)
    except ValueError:
        p_idx = 0
        
    ai_provider = st.selectbox(
        "Preferred AI Engine Model",
        provider_options,
        index=p_idx,
        help="Select the AI Client interface to run classification."
    )

    # API Key Input
    saved_key = config_mgr.get_api_key()
    api_key_input = st.text_input(
        "AI Provider API Key / Secret Key",
        value=saved_key,
        type="password",
        help="The authentication key used to query the selected AI platform. Encrypted locally using DPAPI."
    )

    # Batch Size Settings
    current_batch = config.get("batch_size", 20)
    batch_size = st.slider(
        "AI Batch Request Size",
        min_value=5,
        max_value=50,
        value=current_batch,
        step=5,
        help="Configures the batch size of unique transactions sent in each API call."
    )

    # Cache & Save configurations
    enable_cache = st.toggle("Enable Local Embeddings Cache", value=config.get("auto_save", True), help="Cache transaction signatures locally to prevent repeating AI calls.")
    
    # Auto-update mock trigger
    st.write("")
    st.write("### 🔄 Application Software Updates")
    col_up1, col_up2 = st.columns([1, 2])
    with col_up1:
        if st.button("Check for Software Updates", type="secondary"):
            st.info("AuraLedgerIQ is up to date (Version 1.0.0)")
            
    st.write("")
    st.write("### 🔒 Account & Security")
    with st.form("change_password_form", clear_on_submit=True):
        current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password", help="At least 6 characters.")
        confirm_password = st.text_input("Confirm New Password", type="password")

        if st.form_submit_button("🔑 Update Password", type="secondary"):
            if new_password != confirm_password:
                st.error("New password and confirmation do not match.")
            else:
                success, message = change_password(current_password, new_password)
                if success:
                    st.success(message)
                else:
                    st.error(message)

    st.write("")
    if st.button("💾 Save System Configurations", type="primary"):
        # Save to config
        config["ai_provider"] = ai_provider
        config["batch_size"] = batch_size
        config["auto_save"] = enable_cache

        # Save key
        config_mgr.set_api_key(api_key_input)
        if config_mgr.save_config(config):
            st.success("System configurations successfully encrypted and saved.")
        else:
            st.error("Failed to save local configurations.")

    render_footer()
