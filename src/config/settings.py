import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from workspace root
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def _get_setting(key: str, default: str = "") -> str:
    """
    Reads a setting from the OS environment first (.env locally), then falls
    back to st.secrets (Streamlit Cloud's secrets manager, which does not
    populate OS environment variables). Streamlit isn't importable outside a
    running app context in every case, so the import is guarded rather than
    module-level.
    """
    value = os.getenv(key, "")
    if value:
        return value
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


# Bank Statement Files
INPUT_FILE = os.getenv("INPUT_FILE", "input/BankStatement.xls")
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "output/BankStatement_Classified.xlsx")

# AI Settings
AI_PROVIDER = _get_setting("AI_PROVIDER", "gemini")  # Options: gemini, openai
GEMINI_API_KEY = _get_setting("GEMINI_API_KEY", "")
GEMINI_MODEL = _get_setting("GEMINI_MODEL", "gemini-2.5-flash")

OPENAI_API_KEY = _get_setting("OPENAI_API_KEY", "")
OPENAI_MODEL = _get_setting("OPENAI_MODEL", "gpt-4.1-mini")

# Cache Configuration
CACHE_FILE = os.getenv("CACHE_FILE", "cache/classified_cache.json")

# Batch Configuration
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "20"))

# PDF/OCR Settings
# Empty means "assume it's on PATH" (true for a normal Tesseract/Poppler install with an installer).
# Set these explicitly if Tesseract/Poppler were installed to a non-standard location.
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "")
POPPLER_PATH = os.getenv("POPPLER_PATH", "")
