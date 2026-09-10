import re
import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple

import pandas as pd

from parsers.base_parser import BaseParser, InvalidStatementException

logger = logging.getLogger("AuraLedger")


class BasePDFParser(BaseParser):
    """
    Shared machinery for bank-specific PDF statement parsers (word-position
    extraction, line clustering, footer exclusion, transaction-line walking).

    A concrete bank parser (e.g. HDFCPDFParser) only needs to supply:
      - HEADER_KEYWORDS: words that must all appear on a line for it to be the
        transaction table's header row
      - `_get_header_context()`: any per-statement setup derived from the header
        line (e.g. column x-spans needed to disambiguate debit vs credit)
      - `_parse_transaction_line()`: recognizes this bank's fields on one line

    This exists because real bank PDF layouts turn out to need genuinely
    bank-specific field recognition (see HDFCPDFParser's docstring for why a
    naive header-position-anchor approach fails even for one bank) -- but the
    surrounding mechanics (rendering words into lines, walking those lines,
    merging narration continuation lines, stopping at the footer) are the same
    problem for every bank and shouldn't be re-implemented per parser.
    """

    HEADER_KEYWORDS: set = set()  # subclasses must override
    GENERIC_FOOTER_MARKERS = (
        "statementsummary", "generatedon", "registeredoffice", "closingbalanceincludes",
        "contentsofthisstatement", "thisisacomputergenerated",
    )
    FOOTER_MARKERS: tuple = GENERIC_FOOTER_MARKERS  # subclasses may extend with bank-specific literals
    DATE_PATTERN = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")
    MONEY_PATTERN = re.compile(r"^[\d,]+\.\d{2}$")
    REF_PATTERN = re.compile(r"^\d{8,}$")
    ROW_TOLERANCE = 3

    def parse(self, file_path: Path) -> pd.DataFrame:
        import pdfplumber

        file_path = Path(file_path)
        logger.info(f"Parsing {self.__class__.__name__} PDF statement: {file_path.name}")

        all_rows = []
        page_count = 0
        try:
            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                for page in pdf.pages:
                    words = page.extract_words()
                    if words:
                        all_rows.extend(self._extract_page_transactions(words))
        except InvalidStatementException:
            raise
        except Exception as e:
            raise InvalidStatementException(f"Error reading PDF: {e}")

        # Readable by the caller after parse() returns -- bank-specific PDF parsers
        # always work from an embedded text layer, never OCR (extract_words() needs
        # real text positions), so this is fixed for the whole BasePDFParser family.
        self.extraction_info = {
            "extraction_method": "digital_text_dedicated_parser",
            "page_count": page_count,
            "text_available": True,
            "table_available": None,
            "ocr_used": False,
        }

        if not all_rows:
            raise InvalidStatementException(
                "No transaction rows could be extracted from this PDF statement."
            )

        df = pd.DataFrame(all_rows, columns=["date", "narration", "reference", "debit", "credit", "balance"])
        return self.common_cleanup(df)

    def _extract_page_transactions(self, words: List[dict]) -> List[dict]:
        lines = self._cluster_words_into_lines(words)

        header_idx = None
        for idx, line in enumerate(lines):
            texts_lower = {w["text"].lower().strip(".:") for w in line}
            if self.HEADER_KEYWORDS.issubset(texts_lower):
                header_idx = idx
                break

        if header_idx is None:
            # No transaction table on this page (e.g. a trailing summary-only page)
            return []

        header_context = self._get_header_context(lines[header_idx])

        transactions = []
        current = None

        for line in lines[header_idx + 1:]:
            texts = [w["text"] for w in line]
            combined_upper = "".join(texts).upper()
            if any(marker.upper() in combined_upper for marker in self.FOOTER_MARKERS):
                break

            if texts and self.DATE_PATTERN.match(texts[0]):
                parsed = self._parse_transaction_line(line, header_context)
                if parsed:
                    if current:
                        transactions.append(current)
                    current = parsed
            elif current:
                # Continuation line: pure narration overflow, no other columns present
                current["narration"] = f"{current['narration']} {' '.join(texts)}".strip()

        if current:
            transactions.append(current)

        return transactions

    def _cluster_words_into_lines(self, words: List[dict]) -> List[List[dict]]:
        """Groups words into physical lines by y-position, sorted left-to-right within each line."""
        words = sorted(words, key=lambda w: w["top"])
        lines: List[List[dict]] = []
        current = [words[0]]
        current_top = words[0]["top"]

        for w in words[1:]:
            if abs(w["top"] - current_top) <= self.ROW_TOLERANCE:
                current.append(w)
            else:
                current.sort(key=lambda x: x["x0"])
                lines.append(current)
                current = [w]
                current_top = w["top"]
        current.sort(key=lambda x: x["x0"])
        lines.append(current)
        return lines

    def _header_span(self, header_line: List[dict], keyword: str) -> Tuple[float, float]:
        """Returns the (x0, x1) span of the header word matching `keyword` (normalized, no punctuation)."""
        for w in header_line:
            normalized = re.sub(r"[^a-z]", "", w["text"].lower())
            if normalized == keyword:
                return (w["x0"], w["x1"])
        return (0.0, 0.0)

    def _get_header_context(self, header_line: List[dict]) -> Any:
        """
        Derives whatever per-statement context this bank's line parser needs from
        the header row (e.g. column x-spans for debit/credit disambiguation).
        Default hook for banks whose layout has a detectable header row and fits
        `_extract_page_transactions`'s default implementation (see HDFCPDFParser).
        Not every bank's layout fits that template -- one with no reliable header
        row, or where a transaction spans lines in a different order, should
        override `_extract_page_transactions` itself instead (see SBIPDFParser).
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must either override _get_header_context "
            "(if using the default _extract_page_transactions) or override "
            "_extract_page_transactions entirely."
        )

    def _parse_transaction_line(self, words: List[dict], header_context: Any) -> Optional[dict]:
        """Recognizes this bank's fields (date/narration/reference/debit/credit/balance) on one line."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must either override _parse_transaction_line "
            "(if using the default _extract_page_transactions) or override "
            "_extract_page_transactions entirely."
        )
