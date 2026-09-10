import sys
import os
import tempfile
import streamlit as st
import pandas as pd
from components.header import render_header
from components.footer import render_footer
from services.storage import get_uploaded_statements, add_uploaded_statement, clear_all_data
from services.classification_service import process_classification
from services.validation import validate_statement_file, FileValidationError

# Ensure src is in paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
from parsers.parser_factory import ParserFactory
from parsers.pdf_parser_factory import PDFParserFactory
from parsers.base_parser import HeaderNotFoundException, InvalidStatementException


def show_upload():
    """
    Renders statement upload and progressive processing panel.
    """
    render_header("Upload Bank Statement", "AuraLedgerIQ automatically extracts and classifies every transaction.")

    st.markdown(
        "<p style='color:#718096; font-size:14px; margin-bottom:4px;'>"
        "<b>Supported banks:</b> HDFC • SBI • ICICI &nbsp;&nbsp;|&nbsp;&nbsp; "
        "<b>Supported formats:</b> Excel • CSV • PDF"
        "</p>",
        unsafe_allow_html=True,
    )

    uploaded_files = st.file_uploader(
        "Drag & drop your statement here, or browse files",
        type=["xls", "xlsx", "csv", "pdf"],
        accept_multiple_files=True
    )

    # Check if files were dropped/uploaded
    if uploaded_files:
        # A genuinely new/changed file selection (not just a rerun triggered by
        # some other widget on the page) replaces whatever was queued before --
        # stale entries from a prior upload (e.g. already-completed statements)
        # shouldn't linger alongside a fresh batch the user just dropped.
        signature = tuple(sorted((f.name, f.size) for f in uploaded_files))
        if st.session_state.get("_upload_signature") != signature:
            clear_all_data()
            st.session_state["_upload_signature"] = signature

        statements = get_uploaded_statements()
        # Verify and add metadata to storage if not already registered
        for file in uploaded_files:
            if not any(s["name"] == file.name for s in statements):
                # Write to temporary file once — reused for both validation and bank detection
                import uuid
                temp_dir = tempfile.gettempdir()
                suffix = os.path.splitext(file.name)[1]
                tmp_path = os.path.join(temp_dir, f"detect_{uuid.uuid4().hex}{suffix}")

                try:
                    with open(tmp_path, "wb") as f:
                        f.write(file.getvalue())

                    # Validate before it's ever queued: extension, size, and readability
                    ext = validate_statement_file(file.name, file.size, tmp_path)

                    if ext == ".pdf":
                        # Fails fast here (e.g. UnsupportedPDFBankException) rather than
                        # waiting until "Magic Categorize" — consistent with every other
                        # rejection reason being caught at upload time, not classify time.
                        PDFParserFactory.get_parser(tmp_path)
                        bank_name = f"{PDFParserFactory.detect_bank(tmp_path)} (PDF)"
                    else:
                        detected = ParserFactory.detect_bank(tmp_path)
                        bank_name = detected.upper() if detected else "Unknown Bank"

                    add_uploaded_statement(file.name, bank_name, file.size)
                    st.success(f"✓ {bank_name} statement detected\n\n✓ {ext.lstrip('.').upper()} format recognized — **{file.name}** is ready to classify.")

                except (FileValidationError, InvalidStatementException) as e:
                    st.error(f"**We couldn't process '{file.name}'**\n\n{e}")
                except Exception as e:
                    st.error(f"**We couldn't process '{file.name}'**\n\nAn unexpected error occurred: {e}")
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)

    # Display Uploaded Statements Table
    statements = get_uploaded_statements()
    if statements:
        STATUS_BADGE = {
            "Uploaded": "🕒 Ready",
            "Processing": "⏳ Processing",
            "Completed": "✅ Completed",
            "Failed": "❌ Failed",
        }

        def _human_size(n):
            n = float(n)
            for unit in ("bytes", "KB", "MB"):
                if n < 1024:
                    return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
                n /= 1024
            return f"{n:.1f} GB"

        with st.container(border=True):
            st.markdown(f"**📋 Ready to classify** &nbsp;·&nbsp; {len(statements)} file(s)")

            df_queue = pd.DataFrame([
                {
                    "File Name": s["name"],
                    "Bank": s["bank"],
                    "Size": _human_size(s["size"]),
                    "Status": STATUS_BADGE.get(s["status"], s["status"]),
                    "Uploaded": s["time"],
                }
                for s in statements
            ])

            st.dataframe(
                df_queue,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "File Name": st.column_config.TextColumn("File Name", width="medium"),
                    "Bank": st.column_config.TextColumn("Bank", width="medium"),
                    "Size": st.column_config.TextColumn("Size", width="small"),
                    "Status": st.column_config.TextColumn("Status", width="small"),
                    "Uploaded": st.column_config.TextColumn("Uploaded", width="medium"),
                },
                height=min(38 * (len(statements) + 1), 250),
            )

            col_clear, col_classify = st.columns([1, 3])
            with col_clear:
                if st.button("🗑️ Clear Queue", type="secondary", use_container_width=True):
                    clear_all_data()
                    st.session_state.pop("_upload_signature", None)
                    st.rerun()

            with col_classify:
                # This is the one deliberate click in the whole flow: classification
                # calls a real, quota-limited external AI API, so it stays an explicit
                # action rather than auto-firing on every file drop. Everything after
                # this click is automatic through to the Results page.
                start_classify = st.button("✨ Classify Transactions", type="primary", use_container_width=True)

        if start_classify:
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                for s in statements:
                    s["status"] = "Processing"

                results = process_classification(uploaded_files, progress_bar, status_text)

                for s in statements:
                    s["status"] = "Completed"

                # Automatic transition to Results -- no "view results" click.
                st.session_state["current_page"] = "Results"
                st.rerun()

            except FileValidationError as e:
                for s in statements:
                    s["status"] = "Failed"
                st.error(f"**We couldn't process this statement**\n\n{e}\n\nTry uploading a different file.")
            except HeaderNotFoundException as e:
                for s in statements:
                    s["status"] = "Failed"
                st.error(
                    "**We couldn't process this statement**\n\n"
                    "We couldn't find a recognizable transaction table in this file. "
                    "This can happen with an unusual layout or an unsupported bank format.\n\n"
                    f"Details: {e}"
                )
            except InvalidStatementException as e:
                for s in statements:
                    s["status"] = "Failed"
                st.error(
                    "**We couldn't process this statement**\n\n"
                    "This doesn't look like a valid bank statement. Possible reasons: an unsupported "
                    "statement format, a password-protected file, or a bank format we don't recognize yet.\n\n"
                    f"Details: {e}"
                )
            except Exception as e:
                for s in statements:
                    s["status"] = "Failed"
                st.error(f"**We couldn't process this statement**\n\nAn unexpected error occurred: {e}")

    else:
        st.markdown("""
            <div class="al-hero">
                <div style="font-size:36px;">📭</div>
                <div class="al-hero-title">No statements uploaded yet</div>
                <div class="al-hero-subtitle">Drag a file into the box above to get started.</div>
            </div>
        """, unsafe_allow_html=True)

    render_footer()
