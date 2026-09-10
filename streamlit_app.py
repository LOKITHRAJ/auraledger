"""Compatibility entry point for Streamlit-hosted deployments.

This file mirrors the main app entry so the project can be launched with
`streamlit run streamlit_app.py` while reusing the existing app logic.
"""

from app import *  # noqa: F401,F403
