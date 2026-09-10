import streamlit as st
import pandas as pd
from components.header import render_header
from components.metrics import render_kpi_card
from components.charts import render_debit_credit_trend
from components.footer import render_footer
from components.theme import COLORS


def show_dashboard():
    """
    Renders the main dashboard: a clear "upload your statement" call to action
    when there's nothing to show yet, or a compact set of KPIs + one trend
    chart once a statement has been classified. Deeper category/expense
    breakdowns live on the Transactions (Results) page, not here.
    """
    render_header("Dashboard", "Your bank statement portfolio at a glance.")

    txns = st.session_state.get("classified_transactions", [])

    if not txns:
        st.markdown("""
            <div class="al-hero">
                <div style="font-size:40px;">📊</div>
                <div class="al-hero-title">Nothing here yet</div>
                <div class="al-hero-subtitle">
                    Upload your HDFC, SBI, or ICICI bank statement (Excel or PDF) and
                    AuraLedgerIQ will automatically extract and classify every transaction.
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.write("")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("📤 Upload Bank Statement", type="primary", use_container_width=True):
                st.session_state["current_page"] = "Upload"
                st.rerun()
        with col_b:
            if st.button("✨ Load Sample Portfolio", use_container_width=True):
                sample_txns = [
                    {"date": "2026-07-01", "narration": "UPI-INFOSYS SALARY-SALARY TRANSFER", "debit": 0.0, "credit": 95000.0, "balance": 95000.0, "category": "Salary Received", "nature": "UPI", "description": "Salary received from Infosys", "confidence": 100, "source_file": "Sample_HDFC_Statement.xlsx"},
                    {"date": "2026-07-02", "narration": "ATM CASH WITHDRAWAL - HDFC BANK", "debit": 15000.0, "credit": 0.0, "balance": 80000.0, "category": "Cash Withdrawal", "nature": "ATM", "description": "Cash withdrawn through ATM", "confidence": 98, "source_file": "Sample_HDFC_Statement.xlsx"},
                    {"date": "2026-07-04", "narration": "UPI-SWIGGY FOOD DELIVERY-GPAY", "debit": 450.0, "credit": 0.0, "balance": 79550.0, "category": "Miscellaneous", "nature": "Miscellaneous", "description": "Small value transaction", "confidence": 100, "source_file": "Sample_HDFC_Statement.xlsx"},
                    {"date": "2026-07-05", "narration": "TANGEDCO ELECTRICITY BILL PAY", "debit": 4200.0, "credit": 0.0, "balance": 75350.0, "category": "Electricity & Utilities", "nature": "Bank Transfer", "description": "Electricity bill paid to TANGEDCO", "confidence": 96, "source_file": "Sample_HDFC_Statement.xlsx"},
                    {"date": "2026-07-07", "narration": "HPCL FUEL PURCHASE - DIESEL", "debit": 3500.0, "credit": 0.0, "balance": 71850.0, "category": "Travel & Conveyance", "nature": "POS", "description": "Fuel expense paid to HPCL", "confidence": 95, "source_file": "Sample_HDFC_Statement.xlsx"},
                    {"date": "2026-07-10", "narration": "DNC CHITS PVT LTD - RETAINER CR", "debit": 0.0, "credit": 45000.0, "balance": 116850.0, "category": "Professional Income", "nature": "NEFT", "description": "Professional fees from DNC Chits", "confidence": 94, "source_file": "Sample_HDFC_Statement.xlsx"},
                    {"date": "2026-07-12", "narration": "LIC METROPOLITAN INSURANCE PREM", "debit": 12500.0, "credit": 0.0, "balance": 104350.0, "category": "Insurance", "nature": "ECS", "description": "Insurance premium paid to LIC", "confidence": 96, "source_file": "Sample_HDFC_Statement.xlsx"},
                    {"date": "2026-07-14", "narration": "UPI-APOLLO PHARMACY DRUG STORE", "debit": 350.0, "credit": 0.0, "balance": 104000.0, "category": "Miscellaneous", "nature": "Miscellaneous", "description": "Small value transaction", "confidence": 100, "source_file": "Sample_HDFC_Statement.xlsx"},
                    {"date": "2026-07-15", "narration": "SBI FIXED DEPOSIT OPENING DR", "debit": 50000.0, "credit": 0.0, "balance": 54000.0, "category": "Fixed Deposit", "nature": "Bank Transfer", "description": "Fixed Deposit created with SBI", "confidence": 98, "source_file": "Sample_HDFC_Statement.xlsx"},
                ]
                st.session_state["classified_transactions"] = sample_txns
                st.session_state["uploaded_statements"] = [
                    {"name": "Sample_HDFC_Statement.xlsx", "bank": "HDFC BANK", "size": 15240, "status": "Completed", "time": "2026-07-15 11:00:00"}
                ]
                st.rerun()

        render_footer()
        return

    df = pd.DataFrame(txns)
    if "source_file" not in df.columns:
        df["source_file"] = "Statement_1.xlsx"

    unique_files = sorted(list(df["source_file"].dropna().unique()))
    selected_file = st.selectbox(
        "Filter by statement",
        ["All Statements"] + unique_files,
        label_visibility="collapsed" if len(unique_files) <= 1 else "visible",
    )
    df_filtered = df[df["source_file"] == selected_file] if selected_file != "All Statements" else df

    total_debit = float(df_filtered["debit"].sum())
    total_credit = float(df_filtered["credit"].sum())
    net_flow = total_credit - total_debit
    flow_sign = "+" if net_flow >= 0 else "-"
    flow_color = COLORS["success"] if net_flow >= 0 else COLORS["danger"]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("Transactions", f"{len(df_filtered):,}", "🔢", COLORS["primary"])
    with col2:
        render_kpi_card("Income", f"₹ {total_credit:,.0f}", "💰", COLORS["success"])
    with col3:
        render_kpi_card("Expenses", f"₹ {total_debit:,.0f}", "💸", COLORS["danger"])
    with col4:
        render_kpi_card("Net Cash Flow", f"{flow_sign}₹ {abs(net_flow):,.0f}", "📈", flow_color)

    st.write("")

    st.markdown('<div class="al-card">', unsafe_allow_html=True)
    render_debit_credit_trend(df_filtered)
    st.markdown('</div>', unsafe_allow_html=True)

    render_footer()
