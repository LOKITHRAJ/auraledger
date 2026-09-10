import re
from typing import List, Dict, Any


class PIIAnonymizer:
    """
    Responsible for identifying and masking PII (Personally Identifiable Information)
    in bank transaction narrations to protect client privacy.
    """

    def __init__(self) -> None:
        # Regex Patterns
        # UPI ID: matches user@bank where bank is a 2 to 10 character alphabetic handle.
        # It handles hyphens and dots in user part safely.
        self.upi_pattern = re.compile(r"\b[a-zA-Z0-9.\-_]+@[a-zA-Z]{2,10}\b", re.IGNORECASE)
        
        # IFSC Code: 4 characters, 0, then 6 alphanumeric characters
        self.ifsc_pattern = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.IGNORECASE)
        
        # Mobile Number: 10 digits (optionally prefixed with +91, 91, or 0)
        self.mobile_pattern = re.compile(r"\b(?:\+?91|0)?[6-9]\d{9}\b")
        
        # Matches typical bank account, card numbers, or loan accounts (9 to 18 digits)
        # Also handles partially masked account numbers containing X, x, or * (e.g. XXXXXXXXXXX9673)
        self.account_pattern = re.compile(r"\b(?:[xX\*]{4,}\d{3,10}|\d{9,18})\b")
        
        # Matches common transaction references:
        # - 12-digit numeric strings (e.g., IMPS/UPI ref numbers like 120869611907)
        # - NEFT/RTGS transaction IDs (starting with N, R, I followed by alphanumeric strings of length 11-21)
        self.ref_pattern = re.compile(
            r"\b(?:\d{12}|[NRI][A-Z0-9]{11,21})\b", re.IGNORECASE
        )

        # Indian names are often preceded by keywords like PAY TO, TRANSFER TO, BY, TO, etc.
        # The keyword itself is matched case-insensitively (preprocessor emits e.g. "Payment to NAME"),
        # but the captured name group stays restricted to uppercase letters so we don't mask ordinary sentences.
        self.transfer_name_pattern = re.compile(
            r"\b(?:(?i:PAY TO|TRANSFER TO|TRANSFER FROM|RECEIPT FROM|BY|TO|FROM|REFUND TO|DEAR))\s+([A-Z\s]{3,25})\b"
        )
        
        # Set of common banking/transaction keywords that should NOT be masked as names
        self.ignored_keywords = {
            "UPI", "IMPS", "NEFT", "RTGS", "CHQ", "CHEQUE", "TRANSFER", "PAY", "TO", "BY", 
            "DEBIT", "CREDIT", "INTEREST", "CHARGES", "COMMISSION", "GST", "TDS", "TAX", 
            "REFUND", "LOAN", "CASH", "WITHDRAWAL", "DEPOSIT", "ATM", "SALARY", "RENT", 
            "FUEL", "INSURANCE", "BILL", "ELECTRICITY", "MOBILE", "UTILITY", "REVERSAL", 
            "SWEEP", "FDR", "AUTO", "SWG", "ZOMATO", "SWIGGY", "AMAZON", "FLIPKART", 
            "UBER", "OLA", "AIRTEL", "JIO", "VI", "HDFC", "ICICI", "SBI", "AXIS"
        }

    def anonymize_narration(self, narration: str) -> str:
        """
        Cleans and masks sensitive details in the narration.
        """
        if not narration or not isinstance(narration, str):
            return ""

        masked = narration.strip()

        # 1. Mask UPI IDs
        masked = self.upi_pattern.sub("[UPI]", masked)

        # 2. Mask IFSC Codes
        masked = self.ifsc_pattern.sub("[IFSC]", masked)

        # 3. Mask Mobile Numbers
        masked = self.mobile_pattern.sub("[PHONE]", masked)

        # 4. Mask UTR/Reference numbers
        masked = self.ref_pattern.sub("[REF]", masked)

        # 5. Mask Account / Card / Loan numbers
        masked = self.account_pattern.sub("[NUM]", masked)

        # 6. Mask customer names based on surrounding transaction keywords
        def name_replacer(match: re.Match) -> str:
            full_match = match.group(0)
            name_part = match.group(1).strip()
            
            # If the matched name consists entirely of non-ignored uppercase words, mask it
            words = [w for w in name_part.split() if w]
            if not words:
                return full_match
                
            # If the words are all uppercase and not in our ignored keywords list
            if all(w.isupper() and w not in self.ignored_keywords for w in words):
                masked_name = " ".join(["[NAME]" for _ in words])
                return full_match.replace(name_part, masked_name)
            
            return full_match

        masked = self.transfer_name_pattern.sub(name_replacer, masked)

        # 7. Clean up multiple/duplicate spaces or dashes resulting from masking
        masked = re.sub(r"\s+", " ", masked)
        masked = re.sub(r"-+", "-", masked)
        masked = masked.strip("- ")
        
        return masked

    def anonymize_transactions(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Returns a new list of transactions with their narrations anonymized.
        """
        anonymized = []
        for txn in transactions:
            anonymized_txn = txn.copy()
            anonymized_txn["narration"] = self.anonymize_narration(txn.get("narration", ""))
            anonymized.append(anonymized_txn)
        return anonymized
