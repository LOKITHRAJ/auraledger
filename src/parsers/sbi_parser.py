import logging
import re
from pathlib import Path
import pandas as pd
from parsers.base_parser import BaseParser, HeaderNotFoundException

logger = logging.getLogger("AuraLedger")


class SBIParser(BaseParser):
    """
    Parser for State Bank of India (SBI) Excel statements.
    Handles multi-line narration continuation rows and filters headers/footers.
    """

    def parse(self, file_path: Path) -> pd.DataFrame:
        logger.info(f"Parsing SBI statement: {file_path}")
        
        try:
            preview = pd.read_excel(file_path, header=None, dtype=str)
        except Exception as e:
            logger.error(f"Failed to read SBI file: {e}")
            from parsers.base_parser import InvalidStatementException
            raise InvalidStatementException(f"Error reading file: {e}")

        # Detect transaction header
        expected_keywords = [
            "date",
            "details",
            "ref no/cheque no",
            "debit",
            "credit",
            "balance"
        ]

        header_row = None
        for index, row in preview.iterrows():
            row_text = " ".join([str(x).lower() for x in row.fillna("")])
            score = sum(1 for kw in expected_keywords if kw in row_text)
            if score >= 4:  # At least 4 columns matched
                header_row = index
                break

        if header_row is None:
            raise HeaderNotFoundException("SBI transaction header row not found.")

        logger.info(f"Detected SBI header row at index: {header_row}")

        # Read starting from header row
        df = pd.read_excel(file_path, header=header_row)

        # Columns mapping
        column_mapping = {
            "date": ["date"],
            "narration": ["details", "narration", "particulars"],
            "reference": ["ref no/cheque no", "ref no", "reference", "cheque no", "chq no"],
            "debit": ["debit", "withdraw"],
            "credit": ["credit", "deposit"],
            "balance": ["balance", "bal"]
        }

        mapped_columns = {}
        df_cols = [str(c).strip() for c in df.columns]

        for std_key, patterns in column_mapping.items():
            matched_col = None
            for col in df_cols:
                if col.lower() in [p.lower() for p in patterns]:
                    matched_col = col
                    break
            if not matched_col:
                for col in df_cols:
                    if any(p in col.lower() for p in patterns):
                        matched_col = col
                        break
            if matched_col:
                mapped_columns[std_key] = matched_col
            else:
                raise HeaderNotFoundException(f"Required SBI column mapping not found for '{std_key}'")

        # Rename columns to standardized names
        df = df.rename(columns={v: k for k, v in mapped_columns.items()})

        # Merge continuation rows where Date is NaN/empty but details/narration exists
        cleaned_rows = []
        last_txn = None
        
        date_pattern = (
            r"^\s*(?:\d{1,2}[/\-\s](?:\d{1,2}|[A-Za-z]{3})[/\-\s]\d{2,4}"
            r"|\d{4}[/\-\s]\d{1,2}[/\-\s]\d{1,2})\s*$"
        )

        for _, row in df.iterrows():
            date_val = str(row.get("date", "")).strip()
            if date_val.lower() in ("nan", "nat", ""):
                date_val = None
                
            narration_val = str(row.get("narration", "")).strip()
            if narration_val.lower() in ("nan", ""):
                narration_val = ""

            # Check if continuation row (date is empty but narration exists)
            if not date_val and narration_val:
                if last_txn:
                    # Append narration text to the previous transaction
                    last_txn["narration"] = (last_txn["narration"] + " " + narration_val).strip()
                continue

            # If new transaction row
            if date_val:
                if re.match(date_pattern, date_val):
                    if last_txn:
                        cleaned_rows.append(last_txn)
                    last_txn = {
                        "date": date_val,
                        "narration": narration_val,
                        "reference": str(row.get("reference", "")).strip(),
                        "debit": row.get("debit"),
                        "credit": row.get("credit"),
                        "balance": row.get("balance")
                    }
                else:
                    # Non-date row (e.g. totals or summary headers)
                    pass

        if last_txn:
            cleaned_rows.append(last_txn)

        df_cleaned = pd.DataFrame(cleaned_rows)
        return self.common_cleanup(df_cleaned)
