import sys
import os
import streamlit as st

# Set standard page configs
st.set_page_config(
    page_title="AuraLedgerIQ - AI-Powered Bank Statement Intelligence",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ensure services/, components/, and src/ packages are visible in paths
root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, "src"))

# Shared design system, injected once per session (not once per component call)
from components.theme import inject_theme
inject_theme()

# Main Authentication & Session Routing
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if "current_page" not in st.session_state:
    st.session_state["current_page"] = "Dashboard"

if not st.session_state["authenticated"]:
    # Import and run login screen
    import screens.Login as Login
    Login.show_login()
else:
    # Load sidebar navigation
    from components.sidebar import render_sidebar
    render_sidebar()
    
    # Page router
    current = st.session_state["current_page"]
    
    if current == "Dashboard":
        import screens.Dashboard as Dashboard
        Dashboard.show_dashboard()
    elif current == "Upload":
        import screens.Upload as Upload
        Upload.show_upload()
    elif current == "Results":
        import screens.Results as Results
        Results.show_results()
    elif current == "Settings":
        import screens.Settings as Settings
        Settings.show_settings()
