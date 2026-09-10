import streamlit as st
from typing import List, Dict, Any

def get_uploaded_statements() -> List[Dict[str, Any]]:
    """
    Retrieves the list of uploaded bank statements metadata.
    """
    if "uploaded_statements" not in st.session_state:
        st.session_state["uploaded_statements"] = []
    return st.session_state["uploaded_statements"]

def add_uploaded_statement(name: str, bank: str, size: int) -> None:
    """
    Registers a new statement in storage.
    """
    import datetime
    statements = get_uploaded_statements()
    statements.append({
        "name": name,
        "bank": bank,
        "size": size,
        "status": "Uploaded",
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

def clear_all_data() -> None:
    """
    Clears all uploaded data and intermediate classification status.
    """
    st.session_state["uploaded_statements"] = []
    st.session_state["transactions"] = []
    st.session_state["classified_transactions"] = []
