import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger("AuraLedger")


class TransactionPreprocessor:
    """
    Pre-processing engine that executes before calling the AI classifier.
    Handles narration cleaning, counterparty extraction, keyword-based rule matching
    (bank charges, GST, interest credits, ATM withdrawals), and small-value auto-classification.
    """

    # (category, nature, description, keywords, direction) — direction is "debit", "credit", or "any".
    # Matched against the raw uppercased narration; first match wins, checked in this order.
    KEYWORD_RULES = [
        # GST is checked first: a narration like "GST ON SMS CHARGES" should be tracked as a
        # tax line item for audit purposes even though it also mentions a bank charge.
        ("Taxes", "GST", "GST levied on a bank charge or fee", [
            "GST", "IGST", "CGST", "SGST"
        ], "debit"),
        ("Bank Charges", "Bank Charges", "Bank-levied fee or service charge", [
            "AMB CHARGE", "AMB CHG", "SMS CHARGE", "SMS CHG", "ANNUAL FEE", "ANNUAL MAINTENANCE",
            "PENAL CHARGE", "PENALTY CHARGE", "MIN BAL CHARGE", "MINIMUM BALANCE CHARGE",
            "SERVICE CHARGE", "SERVICE CHG", "PROCESSING FEE", "LATE FEE", "CHEQUE BOUNCE",
            "CHQ BOUNCE", "ECS RETURN CHARGE", "ECS RETURN CHG", "DEBIT CARD FEE", "DEBIT CARD AMC",
            "FOLIO CHARGE", "NON MAINTENANCE CHARGE", "NON-MAINTENANCE", "AMC CHARGE"
        ], "debit"),
        ("Interest Income", "Interest Credit", "Savings account interest credited by the bank", [
            "INTEREST CREDIT", "INT.PD", "INT PD", "INTEREST PAID", "SB INT", "SAVINGS INTEREST",
            "INTEREST CR", "CREDIT INTEREST"
        ], "credit"),
        ("Cash Withdrawal", "ATM Withdrawal", "Cash withdrawn at an ATM", [
            "ATM WDL", "ATM CASH", "ATM-WDL", "ATW", "CASH WITHDRAWAL", "CASH WDL", "NWD",
            "ATM TRANSACTION"
        ], "debit"),
    ]

    def apply_keyword_rules(self, narration: str, debit_val: float, credit_val: float):
        """
        Checks the narration against known Indian-bank keyword patterns for charges,
        GST, interest credits, and ATM withdrawals. Returns a dict with category/nature/
        description if a rule matches, or None if no rule applies.
        """
        if not narration:
            return None

        text = narration.upper()

        for category, nature, description, keywords, direction in self.KEYWORD_RULES:
            if direction == "debit" and debit_val <= 0:
                continue
            if direction == "credit" and credit_val <= 0:
                continue
            if any(kw in text for kw in keywords):
                return {"category": category, "nature": nature, "description": description}

        return None

    def normalize_narration(self, narration: str) -> str:
        """
        Cleans narration by removing transaction IDs, IFSC codes, UTR numbers, account numbers,
        UPI handles, and duplicate separators.
        """
        if not narration:
            return ""

        text = narration.strip()

        # 1. Remove UPI handles (e.g. name@oksbi, @ybl, etc.)
        text = re.sub(r'[a-zA-Z0-9.\-_]+@[a-zA-Z0-9.\-_]+', '', text)

        # 2. Remove IFSC codes (typically 4 letters, '0', 6 alphanumeric characters)
        text = re.sub(r'\b[A-Za-z]{4}0[A-Za-z0-9]{6}\b', '', text)

        # 3. Split adjacent digits and letters (to preserve names attached to reference numbers)
        text = re.sub(r'(\d)([A-Za-z])', r'\1 \2', text)
        text = re.sub(r'([A-Za-z])(\d)', r'\1 \2', text)

        # 4. Remove long numeric IDs, UTRs, account numbers (8 or more digits)
        text = re.sub(r'\b\d{8,}\b', '', text)

        # 5. Remove mixed alphanumeric transaction/reference IDs (length >= 8 containing at least one digit)
        text = re.sub(r'\b(?=\w*\d)\w{8,}\b', '', text)

        # 6. Replace duplicate/special separators '--', '::', '//' with single spaces
        text = text.replace('--', ' ').replace('::', ' ').replace('//', ' ')

        # 7. Replace multiple consecutive spaces with a single space
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def extract_counterparty(self, narration: str) -> str:
        """
        Extracts the counterparty name from UPI transactions starting with UPI- or UPI/.
        """
        if not narration:
            return ""

        narration_upper = narration.upper()
        if narration_upper.startswith("UPI-") or narration_upper.startswith("UPI/"):
            # Normalize split character to hyphen
            norm_narr = narration.replace("/", "-")
            parts = [p.strip() for p in norm_narr.split("-") if p.strip()]
            if len(parts) > 1:
                candidate = parts[1]
                # Validate candidate is not a UPI handle, IFSC code, or number
                if "@" not in candidate and not candidate.isdigit() and len(candidate) > 0:
                    return candidate
        return ""

    def preprocess(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Preprocesses a list of transactions.
        Auto-classifies transactions with amount < 1000.
        Sets normalized_narration, counterparty, and requires_ai flag for each.
        """
        logger.info(f"Running preprocessing engine on {len(transactions)} transactions.")
        processed_list = []

        for txn in transactions:
            merged = txn.copy()
            orig_narration = merged.get("narration", "")

            # Ensure all required fields exist
            merged["normalized_narration"] = ""
            merged["counterparty"] = ""
            merged["category"] = merged.get("category", "")
            merged["description"] = merged.get("description", "")
            merged["nature"] = merged.get("nature", "")
            merged["confidence"] = merged.get("confidence", 0)
            merged["requires_ai"] = True

            # Extract fields
            counterparty = self.extract_counterparty(orig_narration)
            merged["counterparty"] = counterparty

            import math
            def _clean_val(v):
                try:
                    f = float(v or 0.0)
                    return 0.0 if math.isnan(f) else f
                except Exception:
                    return 0.0

            debit_val = _clean_val(merged.get("debit", 0.0))
            credit_val = _clean_val(merged.get("credit", 0.0))
            active_amount = max(debit_val, credit_val)

            # Generate normalized narration
            if counterparty:
                if debit_val > 0:
                    normalized = f"UPI Payment to {counterparty}"
                elif credit_val > 0:
                    normalized = f"UPI Receipt from {counterparty}"
                else:
                    normalized = self.normalize_narration(orig_narration)
            else:
                normalized = self.normalize_narration(orig_narration)

            merged["normalized_narration"] = normalized

            # Rule 1: Keyword-based rules (bank charges, GST, interest credit, ATM withdrawal)
            rule_match = self.apply_keyword_rules(orig_narration, debit_val, credit_val)

            # Rule 2: Small Value Transactions (< 1000), only if no keyword rule already matched
            if rule_match:
                merged["category"] = rule_match["category"]
                merged["nature"] = rule_match["nature"]
                merged["description"] = rule_match["description"]
                merged["confidence"] = 100
                merged["requires_ai"] = False
            elif active_amount < 1000:
                merged["category"] = "Miscellaneous"
                merged["description"] = "Small value transaction"
                merged["nature"] = "Miscellaneous"
                merged["confidence"] = 100
                merged["requires_ai"] = False
            else:
                merged["requires_ai"] = True

            processed_list.append(merged)

        return processed_list
