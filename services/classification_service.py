import os
import sys
import shutil
import tempfile
import streamlit as st
from typing import List, Dict, Any

# Ensure src/ is accessible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from excel_reader import ExcelReader
from parsers.pdf_parser_factory import PDFParserFactory
from transaction_builder import TransactionBuilder
from transaction_classifier import TransactionClassifier
from excel_writer import ExcelWriter
from ai_client import get_ai_client
from statement_validator import validate_balance_continuity, flag_duplicate_transactions
from services.validation import validate_statement_file, FileValidationError

def process_classification(uploaded_files, progress_bar, status_text) -> List[Dict[str, Any]]:
    """
    Parses and classifies bank statements sequentially.
    Shows progress metrics via Streamlit controls.
    """
    total_files = len(uploaded_files)
    all_transactions = []
    
    # Check if real API Key is configured in settings
    ai_provider = st.session_state.get("settings_ai_provider", "Gemini")
    mock_mode = True
    
    # Attempt to use real AI client if configured
    try:
        real_client = get_ai_client()
        mock_mode = False
    except Exception:
        real_client = None
        mock_mode = True
        status_text.text("⚠️ No AI API key configured — running in limited mock mode.")

    temp_dir = tempfile.mkdtemp()
    balance_validations = {}  # filename -> validate_balance_continuity() result

    try:
        # Step 1: Parse and Build all transactions
        for idx, file_obj in enumerate(uploaded_files):
            status_text.text(f"📄 Reading statement {idx+1}/{total_files} — {file_obj.name}...")

            # Save uploaded stream to temp file
            temp_path = os.path.join(temp_dir, file_obj.name)
            with open(temp_path, "wb") as f:
                f.write(file_obj.getbuffer())

            # Validate before parsing: extension, size, and readability (catches
            # password-protected/corrupted files with a clean message instead of a raw traceback)
            ext = validate_statement_file(file_obj.name, file_obj.size, temp_path)

            # Read Excel/CSV, or PDF (bank-specific parser if one exists, else the
            # generic digital-table/OCR fallback)
            if ext == ".pdf":
                reader = PDFParserFactory.get_parser(temp_path)
                df = reader.parse(temp_path)
                extraction_info = getattr(reader, "extraction_info", None)
                if extraction_info and extraction_info.get("ocr_used"):
                    status_text.text(f"🔍 Scanned PDF detected — extracting {file_obj.name} via OCR...")
            else:
                reader = ExcelReader()
                df = reader.read_excel(temp_path)

            # Build standard transactions
            builder = TransactionBuilder()
            txns = builder.build_transactions(df)

            # Informational only -- never blocks import (bank charges/rounding can
            # legitimately cause a mismatch); duplicates are flagged, not removed.
            balance_validations[file_obj.name] = validate_balance_continuity(txns)
            flag_duplicate_transactions(txns)

            # Store source filename
            for t in txns:
                t["source_file"] = file_obj.name

            all_transactions.extend(txns)

        if not all_transactions:
            status_text.text("No transactions found in uploaded statements.")
            return []

        # Setup Progress tracking
        total_txns = len(all_transactions)
        status_text.text(f"🔎 Transactions extracted — {total_txns} found. Preparing classification...")
        progress_bar.progress(10)

        # Step 2: Initialize classifier
        classifier = TransactionClassifier(ai_client=real_client)
        
        # We wrap the on_batch_complete callback to update progress
        total_batches = 0
        current_batch = 0
        
        # Run preprocess initially to figure out requires_ai count
        preprocessed = classifier.preprocessor.preprocess(all_transactions)
        txns_to_ai = [t for t in preprocessed if t.get("requires_ai", True)]
        
        total_unique = len(set(
            classifier._generate_key(t.get("normalized_narration", ""), t.get("debit", 0.0))
            for t in txns_to_ai
        ))
        
        batch_size = classifier.batch_size
        total_batches = (total_unique + batch_size - 1) // batch_size if total_unique > 0 else 1
        
        def streamlit_callback(progress_txns):
            nonlocal current_batch
            current_batch += 1
            percent = min(10 + int((current_batch / total_batches) * 85), 95)
            progress_bar.progress(percent)
            status_text.text(
                f"🤖 Classifying transactions — batch {min(current_batch, total_batches)}/{total_batches}..."
            )

        # Run classification
        classified_txns = classifier.classify_transactions(
            all_transactions,
            on_batch_complete=streamlit_callback if total_batches > 0 else None
        )

        progress_bar.progress(100)
        status_text.text(f"✅ Classification complete — {total_txns} transactions processed.")
        
        # Save output excel file to dynamic path
        out_excel = os.path.join(temp_dir, "Classified_Bank_Statement.xlsx")
        writer = ExcelWriter(output_path=out_excel)
        writer.write_classified_excel(classified_txns)
        
        # Read final excel bytes for downloader
        with open(out_excel, "rb") as f:
            classified_bytes = f.read()
            
        st.session_state["classified_excel_bytes"] = classified_bytes
        st.session_state["classified_transactions"] = classified_txns
        st.session_state["balance_validations"] = balance_validations

        return classified_txns
        
    finally:
        shutil.rmtree(temp_dir)
