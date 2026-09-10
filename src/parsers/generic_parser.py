import logging
from pathlib import Path
import pandas as pd
from parsers.base_parser import BaseParser, HeaderNotFoundException, InvalidStatementException

logger = logging.getLogger("AuraLedger")


class GenericParser(BaseParser):
    """
    Best-effort fallback parser used for bank statements that don't match any
    of the known bank signatures (HDFC/SBI/ICICI/Axis/CUB), and for CSV exports.
    Scans the first rows for a recognizable transaction header, then maps columns
    dynamically instead of relying on bank-specific layout knowledge.
    """

    HEADER_SCAN_ROWS = 30

    column_mapping = {
        "date": ["date", "value date", "txn date", "transaction date"],
        "narration": ["narration", "particulars", "description", "remarks", "details"],
        "reference": ["chq./ref.no.", "chq no", "ref no", "reference", "cheque no", "utr"],
        "debit": ["withdrawal amt.", "debit", "withdrawal", "dr"],
        "credit": ["deposit amt.", "credit", "deposit", "cr"],
        "balance": ["closing balance", "balance", "bal", "running balance"]
    }

    def _read_raw(self, file_path: Path, header=None) -> pd.DataFrame:
        if file_path.suffix.lower() == ".csv":
            return pd.read_csv(file_path, header=header, dtype=str)
        return pd.read_excel(file_path, header=header, dtype=str)

    def parse(self, file_path: Path) -> pd.DataFrame:
        logger.info(f"Parsing statement with GenericParser (fallback): {file_path}")

        try:
            preview = self._read_raw(file_path, header=None)
        except Exception as e:
            logger.error(f"Failed to read file for generic parsing: {e}")
            raise InvalidStatementException(f"Error reading file: {e}")

        # Detect the header row by scoring how many known keywords each row contains
        expected_keywords = ["date", "narration", "particulars", "description", "debit", "credit", "withdrawal", "deposit", "balance"]

        header_row = None
        for index, row in preview.head(self.HEADER_SCAN_ROWS).iterrows():
            row_text = " ".join([str(x).lower() for x in row.fillna("")])
            score = sum(1 for kw in expected_keywords if kw in row_text)
            if score >= 3:
                header_row = index
                break

        if header_row is None:
            raise HeaderNotFoundException(
                "Could not detect a transaction table (Date/Narration/Debit/Credit columns) in this file."
            )

        logger.info(f"Detected header row at index: {header_row}")

        df = self._read_raw(file_path, header=header_row)
        df_cols = [str(c).strip() for c in df.columns]

        mapped_columns = {}
        for std_key, patterns in self.column_mapping.items():
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
            elif std_key in ("date", "narration"):
                # Date and narration are required; debit/credit/balance/reference can be backfilled
                raise HeaderNotFoundException(f"Required column not found for '{std_key}'. Detected columns: {df_cols}")

        df = df.rename(columns={v: k for k, v in mapped_columns.items()})

        return self.common_cleanup(df)
