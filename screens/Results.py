import streamlit as st
import pandas as pd
import datetime
from components.header import render_header
from components.tables import render_transaction_table
from components.metrics import render_kpi_card
from components.charts import render_category_donut
from components.footer import render_footer
from components.theme import COLORS

UNCLASSIFIED_CATEGORIES = {"Review Narration", "Unclassified", "Unknown", ""}
NEEDS_REVIEW_CONFIDENCE_THRESHOLD = 70


def needs_review(txn: dict) -> bool:
    """A transaction the AI flagged for manual review: unclassified, or low confidence."""
    if txn.get("category") in UNCLASSIFIED_CATEGORIES:
        return True
    confidence = txn.get("confidence") or 0
    return confidence < NEEDS_REVIEW_CONFIDENCE_THRESHOLD

def run_anomaly_detection(transactions: list) -> list:
    """
    Scans transactions for financial anomalies using rule-based heuristics.
    """
    anomalies = []
    seen_keys = {}  # for duplicate check: (narration, amount, date)
    
    for idx, txn in enumerate(transactions):
        date_str = txn.get("date", "")
        narration = txn.get("narration", "")
        debit = float(txn.get("debit", 0.0) or 0.0)
        credit = float(txn.get("credit", 0.0) or 0.0)
        amount = debit if debit > 0 else credit
        balance = float(txn.get("balance", 0.0) or 0.0)
        nature = txn.get("nature", "").upper()
        confidence = txn.get("confidence", 100)
        category = txn.get("category", "")
        
        # 1. Negative Balance Check
        if balance < 0:
            anomalies.append({
                "title": "Negative Closing Balance",
                "description": f"Transaction on {date_str} leaves balance at negative ₹{balance:,.2f}.",
                "severity": "High",
                "txn": txn
            })
            
        # 2. Large Cash Withdrawal Check
        if debit >= 20000 and (nature == "ATM" or "CASH" in narration.upper() or "WITHDRAW" in narration.upper()):
            anomalies.append({
                "title": "Large Cash Withdrawal",
                "description": f"ATM/Cash Withdrawal of ₹{debit:,.2f} on {date_str}. Narration: {narration}.",
                "severity": "High",
                "txn": txn
            })

        # 3. High Value Transaction Check
        if amount >= 100000:
            anomalies.append({
                "title": "High Value Transaction",
                "description": f"Transaction amount of ₹{amount:,.2f} on {date_str}. Narration: {narration}.",
                "severity": "High",
                "txn": txn
            })
            
        # 4. Duplicate Payments Check
        if amount > 0:
            dup_key = (narration.lower(), amount)
            if dup_key in seen_keys:
                prev_date = seen_keys[dup_key]
                anomalies.append({
                    "title": "Potential Duplicate Payment",
                    "description": f"Identical amount of ₹{amount:,.2f} matching prior transaction on {prev_date}. Narration: {narration}.",
                    "severity": "Medium",
                    "txn": txn
                })
            else:
                seen_keys[dup_key] = date_str

        # 5. Round Amount Check
        if amount >= 10000 and amount % 10000 == 0:
            anomalies.append({
                "title": "Round Amount Payment",
                "description": f"Exact round payment of ₹{amount:,.2f} on {date_str}. Narration: {narration}.",
                "severity": "Low",
                "txn": txn
            })

        # 6. Low Confidence Check
        if confidence < 70 and confidence > 0:
            anomalies.append({
                "title": "Low Confidence AI Classification",
                "description": f"AI classified as '{category}' with only {confidence}% confidence on {date_str}.",
                "severity": "Medium",
                "txn": txn
            })

        # 7. Weekend Transaction Check
        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            if dt.weekday() in (5, 6) and amount >= 10000:
                day_name = "Saturday" if dt.weekday() == 5 else "Sunday"
                anomalies.append({
                    "title": f"Weekend High-Value Activity",
                    "description": f"High value transaction of ₹{amount:,.2f} on {day_name} ({date_str}). Narration: {narration}.",
                    "severity": "Low",
                    "txn": txn
                })
        except Exception:
            pass

    return anomalies

def show_results():
    """
    Renders classification tables, anomaly alerts, search, and downloaders.
    """
    txns = st.session_state.get("classified_transactions", [])

    if not txns:
        render_header("Transactions", "")
        st.markdown("""
            <div class="al-hero">
                <div style="font-size:36px;">📋</div>
                <div class="al-hero-title">No results yet</div>
                <div class="al-hero-subtitle">Upload and classify a bank statement to see your transactions here.</div>
            </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button("📤 Upload Bank Statement", type="primary"):
            st.session_state["current_page"] = "Upload"
            st.rerun()
        render_footer()
        return

    render_header("Classification Complete ✓", f"{len(txns)} transactions classified and ready to review.")

    total_debit = sum(float(t.get("debit") or 0) for t in txns)
    total_credit = sum(float(t.get("credit") or 0) for t in txns)
    review_count = sum(1 for t in txns if needs_review(t))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("Transactions", f"{len(txns):,}", "🔢", COLORS["primary"])
    with col2:
        render_kpi_card("Income", f"₹ {total_credit:,.0f}", "💰", COLORS["success"])
    with col3:
        render_kpi_card("Expenses", f"₹ {total_debit:,.0f}", "💸", COLORS["danger"])
    with col4:
        render_kpi_card("Needs Review", f"{review_count:,}", "🔍", COLORS["warning"])

    st.write("")

    if review_count:
        rc, bc = st.columns([4, 1])
        with rc:
            st.markdown(f"""
                <div class="al-review-banner">
                    <span class="al-review-banner-text">⚠️ {review_count} transaction{"s" if review_count != 1 else ""} need review</span>
                </div>
            """, unsafe_allow_html=True)
        with bc:
            if st.button("Review Now", use_container_width=True):
                # Set the checkbox's own state key before it's instantiated below --
                # the Streamlit-supported way to drive a keyed widget programmatically.
                st.session_state["needs_review_filter"] = True

    st.write("")
    with st.expander("📊 Expense by Category", expanded=False):
        render_category_donut(pd.DataFrame(txns))

    # Statement-level balance validation (informational only -- never blocks
    # import; bank charges/rounding/a partial statement period can legitimately
    # cause a mismatch).
    balance_validations = st.session_state.get("balance_validations", {})
    if balance_validations:
        with st.expander("🧮 Statement Balance Validation", expanded=False):
            for filename, result in balance_validations.items():
                status = result.get("validation_status")
                summary = (
                    f"**{filename}** — {result.get('transaction_count')} txns · "
                    f"Opening ₹{result.get('opening_balance'):,.2f} · "
                    f"Calculated Closing ₹{result.get('calculated_balance'):,.2f} · "
                    f"Statement Closing ₹{result.get('closing_balance'):,.2f}"
                    if status not in (None, "no_transactions") else f"**{filename}** — no transactions to validate"
                )
                if status == "matched":
                    st.success(f"✅ {summary}")
                elif status == "mismatch":
                    st.warning(f"⚠️ {summary} (does not reconcile exactly — verify against the original statement)")
                else:
                    st.info(summary)

    # Tabs for Data View vs Anomalies View
    tab_data, tab_anomalies = st.tabs(["📊 Ledger View", "⚠️ Audit Anomalies"])

    df = pd.DataFrame(txns)

    with tab_data:
        # Filter Sidebar/Controls
        st.write("### 🔍 Filter and Search")
        
        # Search & Filter row
        search_col, filter_col1, filter_col2 = st.columns([2, 1, 1])
        with search_col:
            search_term = st.text_input("Global Search (Narration, Category, Nature, etc.)", placeholder="Type to filter...")
            
        with filter_col1:
            categories_list = ["All"] + sorted(list(df["category"].dropna().unique()))
            selected_cat = st.selectbox("Category Filter", categories_list)
            
        with filter_col2:
            natures_list = ["All"] + sorted(list(df["nature"].dropna().unique()))
            selected_nat = st.selectbox("Nature Filter", natures_list)

        # Date & Amount Filters (collapsible for clean spacing)
        with st.expander("Advanced Range Filters"):
            col_d1, col_d2, col_amt = st.columns(3)
            with col_d1:
                min_debit = st.number_input("Min Debit Amount (₹)", value=0.0)
            with col_d2:
                min_credit = st.number_input("Min Credit Amount (₹)", value=0.0)
            with col_amt:
                min_conf = st.slider("Min AI Confidence (%)", 0, 100, 0)

        show_needs_review_only = st.checkbox(
            f"🔍 Show only transactions needing review ({review_count} flagged)",
            key="needs_review_filter",
        ) if review_count else False

        duplicate_count = sum(1 for t in txns if t.get("is_duplicate"))
        show_duplicates_only = False
        if duplicate_count:
            show_duplicates_only = st.checkbox(
                f"⚠️ Show possible duplicates only ({duplicate_count} flagged — same date/amount/narration/reference as another row; not auto-removed)"
            )

        # Apply selectbox/number input filters
        filtered_txns = txns
        if selected_cat != "All":
            filtered_txns = [t for t in filtered_txns if t.get("category") == selected_cat]
        if selected_nat != "All":
            filtered_txns = [t for t in filtered_txns if t.get("nature") == selected_nat]
        if min_debit > 0:
            filtered_txns = [t for t in filtered_txns if float(t.get("debit") or 0) >= min_debit]
        if min_credit > 0:
            filtered_txns = [t for t in filtered_txns if float(t.get("credit") or 0) >= min_credit]
        if min_conf > 0:
            filtered_txns = [t for t in filtered_txns if int(t.get("confidence") or 0) >= min_conf]
        if show_duplicates_only:
            filtered_txns = [t for t in filtered_txns if t.get("is_duplicate")]
        if show_needs_review_only:
            filtered_txns = [t for t in filtered_txns if needs_review(t)]

        # Table Display
        st.write("")
        st.write(f"Showing **{len(filtered_txns)}** of **{len(txns)}** transactions:")
        
        render_transaction_table(filtered_txns, search_term)

        # Download buttons
        st.write("")
        st.write("### 📥 Exports")
        
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            # We can download the classified bytes created during the classification service step
            classified_bytes = st.session_state.get("classified_excel_bytes", b"")
            if classified_bytes:
                st.download_button(
                    label="📥 Download Classified Ledger Excel (.xlsx)",
                    data=classified_bytes,
                    file_name="AuraLedger_Classified_Statement.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        with col_dl2:
            st.info("Classified exports include full styling, centered dates, bold categories, and auto-fitted grids.")

    with tab_anomalies:
        st.write("### ⚠️ Transaction Anomalies Detection Panel")
        st.write("Rule-based heuristics scanner checking cash-withdrawals, double payments, weekend spikes, and negative offsets.")

        anomalies_list = run_anomaly_detection(txns)
        
        if anomalies_list:
            high_sev = [a for a in anomalies_list if a["severity"] == "High"]
            med_res = [a for a in anomalies_list if a["severity"] == "Medium"]
            low_res = [a for a in anomalies_list if a["severity"] == "Low"]

            # Summaries cards
            c_high, c_med, c_low = st.columns(3)
            c_high.metric("🔴 High Severity Alerts", len(high_sev))
            c_med.metric("🟡 Medium Severity Alerts", len(med_res))
            c_low.metric("🟢 Low Severity Alerts", len(low_res))
            
            st.write("")
            
            # Anomaly details
            for alert in anomalies_list:
                sev = alert["severity"]
                color_map = {"High": "red", "Medium": "orange", "Low": "green"}
                border_color = color_map.get(sev, "grey")
                
                st.markdown(f"""
                    <div style="background-color:white; padding:15px; border-radius:10px; border-left: 6px solid {border_color}; border-top:1px solid #E2E8F0; border-bottom:1px solid #E2E8F0; border-right:1px solid #E2E8F0; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                        <h4 style="margin:0 0 5px 0; color:#1A365D;">[{sev} Severity] {alert['title']}</h4>
                        <p style="margin:0; font-size:13px; color:#4A5568;">{alert['description']}</p>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.success("🎉 Scan Complete. Zero financial anomalies or low confidence alerts detected.")

    render_footer()
