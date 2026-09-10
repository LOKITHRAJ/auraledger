import os
import sys
import bcrypt
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
from config.config_manager import ConfigManager

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin123"


def check_auth() -> bool:
    """
    Checks if user is logged in. Redirects or sets session state if needed.
    """
    return st.session_state.get("authenticated", False)


def _verify_password(password: str) -> bool:
    """
    Verifies a password against the stored bcrypt hash. Falls back to the
    default admin123 password if no custom password has been set yet.
    """
    config = ConfigManager().load_config()
    stored_hash = config.get("admin_password_hash", "")

    if stored_hash:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    return password == DEFAULT_PASSWORD


def login(username, password) -> bool:
    """
    Verify user credentials and set session state.
    """
    if username == DEFAULT_USERNAME and _verify_password(password):
        st.session_state["authenticated"] = True
        st.session_state["username"] = "CA Administrator"
        return True
    return False


def logout():
    """
    Log out the user and clear session state.
    """
    st.session_state["authenticated"] = False
    st.session_state["username"] = None


def change_password(current_password: str, new_password: str):
    """
    Verifies the current password and, if correct, hashes and persists the new one.
    Returns (success: bool, message: str).
    """
    if not _verify_password(current_password):
        return False, "Current password is incorrect."

    if not new_password or len(new_password) < 6:
        return False, "New password must be at least 6 characters long."

    config_mgr = ConfigManager()
    config = config_mgr.load_config()
    config["admin_password_hash"] = bcrypt.hashpw(
        new_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    if config_mgr.save_config(config):
        return True, "Password updated successfully."
    return False, "Failed to save the new password. Please try again."
