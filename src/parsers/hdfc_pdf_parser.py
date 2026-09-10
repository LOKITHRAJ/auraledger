import logging
from typing import List, Optional, Tuple

from parsers.base_pdf_parser import BasePDFParser

logger = logging.getLogger("AuraLedger")


class HDFCPDFParser(BasePDFParser):
    """
    Dedicated parser for HDFC Bank's NetBanking-generated PDF account statements.

    HDFC's PDF layout wraps long narrations across multiple physical lines within
    the table (the renderer avoids column overflow by wrapping, rather than letting
    text run into the next column), so `pdfplumber.extract_tables()` cannot
    correctly split a page's transactions into separate rows -- it collapses them
    all into one newline-joined blob per column.

    It also turns out HDFC's header labels aren't x-aligned with where the actual
    data starts (e.g. "Narration" is printed well to the right of where narration
    text actually begins, which sits almost directly after the Date column) --
    so a header-position-anchor approach misclassifies Date vs Narration. This
    parser instead recognizes each column by its own content pattern (date,
    long reference digits, money amounts) and only falls back to x-position for
    the one thing content can't tell us: whether an amount is a debit or a credit.
    """

    HEADER_KEYWORDS = {"date", "narration"}
    FOOTER_MARKERS = BasePDFParser.GENERIC_FOOTER_MARKERS + (
        "hdfcbanklimited", "hdfcbankltd",
    )

    def _get_header_context(self, header_line: List[dict]) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        withdrawal_span = self._header_span(header_line, "withdrawalamt")
        deposit_span = self._header_span(header_line, "depositamt")
        return withdrawal_span, deposit_span

    def _parse_transaction_line(
        self, words: List[dict], header_context: Tuple[Tuple[float, float], Tuple[float, float]]
    ) -> Optional[dict]:
        withdrawal_span, deposit_span = header_context
        texts = [w["text"] for w in words]

        money_indices = [i for i, t in enumerate(texts) if self.MONEY_PATTERN.match(t)]
        if len(money_indices) < 2:
            # Don't log raw line content -- it can contain real narration/reference data.
            logger.warning(
                f"Skipping malformed HDFC PDF transaction line (missing amount/balance): "
                f"{len(texts)} words, {len(money_indices)} money-like tokens found."
            )
            return None

        balance_idx = money_indices[-1]
        amount_idx = money_indices[-2]
        balance = texts[balance_idx]
        amount = texts[amount_idx]
        amount_word = words[amount_idx]

        debit, credit = self._classify_amount_direction(amount, amount_word["x0"], withdrawal_span, deposit_span)

        value_dt_idx = amount_idx - 1
        has_value_dt = value_dt_idx > 0 and self.DATE_PATTERN.match(texts[value_dt_idx])

        ref_idx = None
        search_end = value_dt_idx if has_value_dt else amount_idx
        for i in range(1, search_end):
            if self.REF_PATTERN.match(texts[i]):
                ref_idx = i
        reference = texts[ref_idx] if ref_idx is not None else ""

        narration_end_idx = ref_idx if ref_idx is not None else search_end
        narration = " ".join(texts[1:narration_end_idx]) if narration_end_idx > 1 else ""

        return {
            "date": texts[0],
            "narration": narration,
            "reference": reference,
            "debit": debit,
            "credit": credit,
            "balance": balance,
        }

    def _classify_amount_direction(
        self, amount: str, amount_x0: float, withdrawal_span: Tuple[float, float], deposit_span: Tuple[float, float]
    ) -> Tuple[str, str]:
        """
        Determines whether a transaction amount is a debit (withdrawal) or credit
        (deposit) by checking which header column's x-span it falls under -- the
        one thing this parser needs position for, since content alone can't
        distinguish a withdrawal amount from a deposit amount.
        """
        in_withdrawal = withdrawal_span[0] <= amount_x0 <= withdrawal_span[1]
        in_deposit = deposit_span[0] <= amount_x0 <= deposit_span[1]

        if in_withdrawal and not in_deposit:
            return amount, ""
        if in_deposit and not in_withdrawal:
            return "", amount

        # Ambiguous (falls in both/neither span, e.g. very short header words) -- fall
        # back to whichever column center is closer.
        withdrawal_center = (withdrawal_span[0] + withdrawal_span[1]) / 2
        deposit_center = (deposit_span[0] + deposit_span[1]) / 2
        if abs(amount_x0 - withdrawal_center) <= abs(amount_x0 - deposit_center):
            return amount, ""
        return "", amount
