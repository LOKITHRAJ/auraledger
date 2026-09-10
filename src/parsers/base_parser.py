from abc import ABC, abstractmethod
from pathlib import Path
import pandas as pd


class UnsupportedBankException(Exception):
    """Raised when the bank type is not supported by the factory."""
    pass


class HeaderNotFoundException(Exception):
    """Raised when the transaction headers cannot be detected in the statement."""
    pass


class InvalidStatementException(Exception):
    """Raised when the statement file is corrupt or has invalid structure."""
    pass


class BaseParser(ABC):
    """
    Abstract Base Class for all bank statement parsers.
    Defines parsing lifecycle and common statement cleanup utilities.
    """

    @abstractmethod
    def parse(self, file_path: Path) -> pd.DataFrame:
        """
        Parses the Excel file and returns a standardized pandas DataFrame
        with exactly: date, narration, reference, debit, credit, balance columns.
        """
        pass

    def common_cleanup(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Applies standard cleanup actions across all bank statement dataframes:
        1. Remove blank rows
        2. Trim whitespace from string columns
        3. Convert amount fields (debit, credit, balance) to numeric
        4. Remove potential repeated header rows
        5. Reset index
        """
        required_cols = ["date", "narration", "reference", "debit", "credit", "balance"]
        
        # Trim all string columns and clean empty cells
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip()
                # Replace string nan/None/NAT with empty string
                df[col] = df[col].replace({"nan": "", "None": "", "NaT": ""})

        # Remove completely blank or empty rows
        subset_cols = [c for c in required_cols if c in df.columns]
        df = df.dropna(how="all", subset=subset_cols)

        # Remove separator lines or headers if they reappear
        if "date" in df.columns:
            df = df[df["date"].str.lower() != "date"]
            df = df[~df["date"].str.contains(r"\*+", regex=True, na=False)]
            df = df[df["date"] != ""]

        # Ensure debit, credit, balance columns are present and numeric
        for col in ["debit", "credit", "balance"]:
            if col in df.columns:
                df[col] = df[col].apply(self._clean_numeric_value)
            else:
                df[col] = 0.0

        # Enforce exact standardized columns and order
        for col in required_cols:
            if col not in df.columns:
                df[col] = "" if col == "reference" else 0.0
                
        df = df[required_cols]
        df = df.reset_index(drop=True)
        return df

    def _clean_numeric_value(self, val) -> float:
        """
        Cleans and parses amount values to floats safely.
        """
        if pd.isna(val) or val is None:
            return 0.0
        val_str = str(val).replace(",", "").replace(" ", "").strip()
        if val_str == "" or val_str == "-" or "*" in val_str:
            return 0.0
        try:
            return float(val_str)
        except ValueError:
            return 0.0
