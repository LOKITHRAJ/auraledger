import streamlit as st
import pandas as pd
from typing import List, Dict, Any
from components.theme import COLORS


def render_transaction_table(transactions: List[Dict[str, Any]], search_term: str = ""):
    """
    Renders the transaction list. Shows a simplified, business-owner-friendly
    column set (Date/Description/Amount/Type/Category/Confidence) -- Debit and
    Credit are combined into one Amount+Type pair for display only. This does
    not touch the underlying transaction dict (still has debit/credit/nature/
    description/reference separately), so export and classification are
    unaffected -- it's a display simplification, not a schema change.
    """
    if not transactions:
        st.info("No transaction data available.")
        return

    df = pd.DataFrame(transactions)

    for col in ["date", "narration", "debit", "credit", "category", "nature", "description", "confidence"]:
        if col not in df.columns:
            df[col] = "" if col in ("date", "narration", "category", "nature", "description") else 0

    # Global search across the full underlying record, even fields not shown by default
    if search_term:
        term = search_term.lower()
        mask = (
            df["narration"].astype(str).str.lower().str.contains(term) |
            df["category"].astype(str).str.lower().str.contains(term) |
            df["nature"].astype(str).str.lower().str.contains(term) |
            df["description"].astype(str).str.lower().str.contains(term) |
            df["date"].astype(str).str.lower().str.contains(term) |
            df["debit"].astype(str).str.contains(term) |
            df["credit"].astype(str).str.contains(term)
        )
        df = df[mask]

    debit = pd.to_numeric(df["debit"], errors="coerce").fillna(0.0)
    credit = pd.to_numeric(df["credit"], errors="coerce").fillna(0.0)

    display_df = pd.DataFrame({
        "date": df["date"],
        "narration": df["narration"],
        "amount": debit.where(debit > 0, credit),
        "type": pd.Series(["Expense" if d > 0 else "Income" for d in debit], index=df.index),
        "category": df["category"],
        "confidence": df["confidence"],
    })

    def style_confidence(val):
        try:
            score = int(str(val).replace("%", "").strip())
        except ValueError:
            score = 0

        if score >= 90:
            return 'background-color: #C6F6D5; color: #22543D; font-weight: bold;'
        elif 70 <= score < 90:
            return 'background-color: #FEEBC8; color: #744210; font-weight: bold;'
        else:
            return 'background-color: #FED7D7; color: #742A2A; font-weight: bold;'

    def style_type(val):
        if val == "Income":
            return f'background-color: #C6F6D5; color: {COLORS["success"]}; font-weight: 600;'
        elif val == "Expense":
            return f'background-color: #FED7D7; color: {COLORS["danger"]}; font-weight: 600;'
        return ''

    styled_df = (
        display_df.style
        .map(style_confidence, subset=['confidence'])
        .map(style_type, subset=['type'])
    )

    st.dataframe(
        styled_df,
        use_container_width=True,
        column_config={
            "date": st.column_config.TextColumn("Date", width="medium"),
            "narration": st.column_config.TextColumn("Description", width="large"),
            "amount": st.column_config.NumberColumn("Amount (₹)", format="₹ %.2f"),
            "type": st.column_config.TextColumn("Type", width="small"),
            "category": st.column_config.TextColumn("Category", width="medium"),
            "confidence": st.column_config.NumberColumn("Confidence (%)", format="%d%%"),
        },
        height=500
    )
