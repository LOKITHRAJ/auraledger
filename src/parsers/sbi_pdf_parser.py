import logging
from typing import List, Optional

from parsers.base_pdf_parser import BasePDFParser

logger = logging.getLogger("AuraLedger")


class SBIPDFParser(BasePDFParser):
    """
    Dedicated parser for State Bank of India's net-banking PDF account statements.

    SBI's layout is structurally different from HDFC's, which is why this
    overrides `_extract_page_transactions` entirely rather than using the
    header-context/per-line hooks HDFCPDFParser relies on:

      - There is no reliably text-extractable header row to detect (SBI renders
        it such that only a stray "Balance" fragment survives extraction) -- so
        table-start detection can't be keyword-based here at all.
      - Each transaction's TYPE ("WDL TFR", "DEP TFR", "ATM WDL", "POS ATM
        PURCH", ...) sits on its own physical line immediately BEFORE the date
        line, not embedded within it -- the opposite order from HDFC.
      - The main data line already contains both dates, the start of the
        narration, and all four trailing fields (Ref No, Debit, Credit,
        Balance) space-separated on one line, with "-" as an explicit
        placeholder for whichever of Debit/Credit is empty -- so, unlike HDFC,
        debit-vs-credit direction is unambiguous from content alone; no
        x-position column-span check is needed.
      - Narration continues across 0-3 further lines with no other fields
        present.
    """

    DATA_LINE_MIN_TOKENS = 6  # 2 dates + Ref No + Debit + Credit + Balance, even with zero narration words
    FOOTER_MARKERS = BasePDFParser.GENERIC_FOOTER_MARKERS + (
        "pageno", "statementsummary", "broughtforward", "pleasedonotshare",
    )

    def _extract_page_transactions(self, words: List[dict]) -> List[dict]:
        lines = self._cluster_words_into_lines(words)
        transactions: List[dict] = []
        current: Optional[dict] = None
        pending_type = ""

        for idx, line in enumerate(lines):
            texts = [w["text"] for w in line]
            if not texts:
                continue

            if self._is_data_line(texts):
                if current:
                    transactions.append(current)
                current = self._build_transaction(texts, pending_type)
                pending_type = ""
                continue

            line_text = " ".join(texts)
            normalized = line_text.replace(" ", "").upper()
            if any(marker.upper() in normalized for marker in self.FOOTER_MARKERS):
                break

            next_texts = [w["text"] for w in lines[idx + 1]] if idx + 1 < len(lines) else []
            if next_texts and self._is_data_line(next_texts):
                # This line is the TYPE prefix for the upcoming transaction (SBI
                # prints it on its own line immediately before the date line),
                # not a continuation of whatever transaction came before it.
                pending_type = line_text
            elif current is not None:
                current["narration"] = f"{current['narration']} {line_text}".strip()
            # else: boilerplate before the first transaction on this page (letterhead
            # fragments, the stray "Balance" header remnant) -- safely ignored.

        if current:
            transactions.append(current)

        return transactions

    def _is_data_line(self, texts: List[str]) -> bool:
        return (
            len(texts) >= self.DATA_LINE_MIN_TOKENS
            and bool(self.DATE_PATTERN.match(texts[0]))
            and bool(self.DATE_PATTERN.match(texts[1]))
        )

    def _build_transaction(self, texts: List[str], pending_type: str) -> dict:
        date = texts[0]
        # texts[1] is the post date (duplicate of value date on every observed
        # row) -- intentionally not used, matching how every other parser in
        # this app uses a single "date" field.
        reference, debit, credit, balance = texts[-4:]
        if reference == "-":
            reference = ""
        narration_start = " ".join(texts[2:-4])
        narration = " ".join(part for part in (pending_type, narration_start) if part).strip()

        return {
            "date": date,
            "narration": narration,
            "reference": reference,
            "debit": debit,
            "credit": credit,
            "balance": balance,
        }
