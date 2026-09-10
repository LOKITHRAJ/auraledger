import logging
from pathlib import Path
import pandas as pd
from parsers.base_parser import BaseParser, HeaderNotFoundException

logger = logging.getLogger("AuraLedger")


class HDFCParser(BaseParser):
    """
    Parser for HDFC Bank Excel statements.
    """

    def parse(self, file_path: Path) -> pd.DataFrame:
        logger.info(f"Parsing HDFC statement: {file_path}")
        
        try:
            preview = pd.read_excel(file_path, header=None, dtype=str)
        except Exception as e:
            logger.error(f"Failed to read HDFC file: {e}")
            from parsers.base_parser import InvalidStatementException
            raise InvalidStatementException(f"Error reading file: {e}")

        # Detect transaction header
        expected_keywords = [
            "date",
            "narration",
            "chq./ref.no.",
            "withdrawal amt.",
            "deposit amt.",
            "closing balance"
        ]

        header_row = None
        for index, row in preview.iterrows():
            row_text = " ".join([str(x).lower() for x in row.fillna("")])
            score = sum(1 for kw in expected_keywords if kw in row_text)
            if score >= 4:  # At least 4 columns matched
                header_row = index
                break

        if header_row is None:
            raise HeaderNotFoundException("HDFC transaction header row not found.")

        logger.info(f"Detected HDFC header row at index: {header_row}")

        # Read starting from header row
        df = pd.read_excel(file_path, header=header_row)

        # Dynamic column mapping
        column_mapping = {
            "date": ["date"],
            "narration": ["narration", "particulars", "description"],
            "reference": ["chq./ref.no.", "chq", "ref", "reference"],
            "debit": ["withdrawal amt.", "debit", "withdrawal"],
            "credit": ["deposit amt.", "credit", "deposit"],
            "balance": ["closing balance", "balance", "bal"]
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
                raise HeaderNotFoundException(f"Required HDFC column mapping not found for '{std_key}'")

        # Rename columns
        df = df.rename(columns={v: k for k, v in mapped_columns.items()})
        df = df[list(column_mapping.keys())]

        # Clean HDFC header/footer
        if "date" in df.columns:
            df["date"] = df["date"].astype(str).str.strip()
            df = df[~df["date"].str.contains(r"\*+", regex=True, na=False)]

            date_pattern = (
                r"^\s*(?:\d{1,2}[/\-\s](?:\d{1,2}|[A-Za-z]{3})[/\-\s]\d{2,4}"
                r"|\d{4}[/\-\s]\d{1,2}[/\-\s]\d{1,2})\s*$"
            )
            df = df[df["date"].str.contains(date_pattern, regex=True, na=False)]

        return self.common_cleanup(df)
