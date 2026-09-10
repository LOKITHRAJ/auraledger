import logging
import re
from pathlib import Path
import pandas as pd
from parsers.base_parser import BaseParser, HeaderNotFoundException

logger = logging.getLogger("AuraLedger")


class ICICIParser(BaseParser):
    """
    Parser for ICICI Bank Excel statements.
    """

    def parse(self, file_path: Path) -> pd.DataFrame:
        logger.info(f"Parsing ICICI statement: {file_path}")
        
        try:
            preview = pd.read_excel(file_path, header=None, dtype=str)
        except Exception as e:
            logger.error(f"Failed to read ICICI file: {e}")
            from parsers.base_parser import InvalidStatementException
            raise InvalidStatementException(f"Error reading file: {e}")

        # Detect transaction header
        expected_keywords = [
            "date",
            "remarks",
            "cheque number",
            "withdrawal amt",
            "deposit amt",
            "balance"
        ]

        header_row = None
        for index, row in preview.iterrows():
            row_text = " ".join([str(x).lower() for x in row.fillna("")])
            score = sum(1 for kw in expected_keywords if kw in row_text)
            if score >= 3:  # At least 3 columns matched
                header_row = index
                break

        if header_row is None:
            raise HeaderNotFoundException("ICICI transaction header row not found.")

        logger.info(f"Detected ICICI header row at index: {header_row}")

        # Read starting from header row
        df = pd.read_excel(file_path, header=header_row)

        # Columns mapping
        column_mapping = {
            "date": ["transaction date", "value date", "date"],
            "narration": ["transaction remarks", "remarks", "narration", "particulars"],
            "reference": ["cheque number", "chq", "ref", "reference"],
            "debit": ["withdrawal amt (inr)", "withdrawal amt", "debit", "withdrawal"],
            "credit": ["deposit amt (inr)", "deposit amt", "credit", "deposit"],
            "balance": ["balance (inr)", "balance", "bal"]
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
                raise HeaderNotFoundException(f"Required ICICI column mapping not found for '{std_key}'")

        # Rename columns to standardized names
        df = df.rename(columns={v: k for k, v in mapped_columns.items()})
        df = df[list(column_mapping.keys())]

        # Clean header/footer
        if "date" in df.columns:
            df["date"] = df["date"].astype(str).str.strip()
            df = df[~df["date"].str.contains(r"\*+", regex=True, na=False)]

            date_pattern = (
                r"^\s*(?:\d{1,2}[/\-\s](?:\d{1,2}|[A-Za-z]{3})[/\-\s]\d{2,4}"
                r"|\d{4}[/\-\s]\d{1,2}[/\-\s]\d{1,2})\s*$"
            )
            df = df[df["date"].str.contains(date_pattern, regex=True, na=False)]

        return self.common_cleanup(df)
