import logging
import pandas as pd
from typing import List, Dict, Any

logger = logging.getLogger("AuraLedger")


class TransactionBuilder:
    """
    Converts a Pandas DataFrame of a bank statement into a list of standardized transaction dictionaries.
    Dynamically maps column headers and safely parses values.
    """

    def __init__(self) -> None:
        # Define candidate patterns (case-insensitive substrings) for column mapping
        self.column_patterns = {
            "date": ["date", "dt", "value dt", "txn dt"],
            "narration": ["narration", "description", "particular", "remark"],
            "reference": ["reference", "ref", "chq", "cheque", "chq./ref.no.", "ref no/cheque no"],
            "debit": ["withdraw", "debit", "dr", "withdrawal amt."],
            "credit": ["deposit", "credit", "cr", "deposit amt."],
            "balance": ["balance", "bal", "closing balance"]
        }

    def _safe_float(self, value: Any) -> float:
        """
        Safely converts any value to a float.
        Returns 0.0 for NaNs, empty strings, asterisks, or other non-numeric text.
        """
        if pd.isna(value):
            return 0.0

        val_str = str(value).replace(",", "").strip()

        if val_str == "" or "*" in val_str or val_str.lower() in ["nan", "none", "nat", "-"]:
            return 0.0

        try:
            return float(val_str)
        except ValueError:
            # In some footers/headers, non-numeric strings might end up in amount columns
            return 0.0

    def _map_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Dynamically detects and maps DataFrame column headers to standard names.
        Raises ValueError if any required column could not be found.
        """
        mapping = {}
        df_cols = [str(c).strip() for c in df.columns]

        for std_key, patterns in self.column_patterns.items():
            matched_col = None
            
            # Step 1: Look for exact case-insensitive matches
            for col in df_cols:
                if col.lower() in [p.lower() for p in patterns]:
                    matched_col = col
                    break
            
            # Step 2: Look for substring matches if exact match wasn't found
            if not matched_col:
                for col in df_cols:
                    col_lower = col.lower()
                    if any(p in col_lower for p in patterns):
                        matched_col = col
                        break
            
            if matched_col:
                mapping[std_key] = matched_col
            else:
                raise ValueError(
                    f"Could not map required transaction column for: '{std_key}'. "
                    f"Available columns: {list(df.columns)}"
                )

        logger.info(f"Dynamically mapped columns: {mapping}")
        return mapping

    def build_transactions(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Iterates over the DataFrame rows and builds standard transaction dictionaries.
        """
        if df.empty:
            logger.warning("Empty DataFrame passed to TransactionBuilder.")
            return []

        mapping = self._map_columns(df)
        
        date_col = mapping["date"]
        narration_col = mapping["narration"]
        reference_col = mapping.get("reference")
        debit_col = mapping["debit"]
        credit_col = mapping["credit"]
        balance_col = mapping["balance"]

        transactions = []
        for index, row in df.iterrows():
            # Build standardized dict
            txn = {
                "date": str(row[date_col]).strip(),
                "narration": str(row[narration_col]).strip(),
                "reference": str(row[reference_col]).strip() if reference_col is not None and reference_col in row else "",
                "debit": self._safe_float(row[debit_col]),
                "credit": self._safe_float(row[credit_col]),
                "balance": self._safe_float(row[balance_col])
            }
            transactions.append(txn)

        logger.info(f"Successfully built {len(transactions)} transactions.")
        return transactions
