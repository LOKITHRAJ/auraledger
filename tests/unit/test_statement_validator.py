import pytest
from statement_validator import validate_balance_continuity, flag_duplicate_transactions


def _txn(date, debit=0.0, credit=0.0, balance=0.0, narration="TEST", reference="REF"):
    return {"date": date, "narration": narration, "reference": reference, "debit": debit, "credit": credit, "balance": balance}


class TestBalanceContinuity:
    def test_matched_balance(self):
        txns = [
            _txn("01/04/25", debit=0, credit=1000, balance=11000),   # opening inferred: 11000 - 1000 = 10000
            _txn("02/04/25", debit=500, credit=0, balance=10500),
            _txn("03/04/25", debit=0, credit=200, balance=10700),
        ]
        result = validate_balance_continuity(txns)
        assert result["validation_status"] == "matched"
        assert result["opening_balance"] == 10000.0
        assert result["closing_balance"] == 10700.0
        assert result["calculated_balance"] == 10700.0
        assert result["transaction_count"] == 3

    def test_mismatched_balance_is_reported_not_rejected(self):
        txns = [
            _txn("01/04/25", debit=0, credit=1000, balance=11000),
            _txn("02/04/25", debit=500, credit=0, balance=9999),  # inconsistent with debit math
        ]
        result = validate_balance_continuity(txns)
        assert result["validation_status"] == "mismatch"
        # Must still return full data -- never raises, never blocks
        assert result["transaction_count"] == 2

    def test_empty_transaction_list(self):
        result = validate_balance_continuity([])
        assert result["validation_status"] == "no_transactions"
        assert result["transaction_count"] == 0


class TestDuplicateDetection:
    def test_no_duplicates_in_distinct_transactions(self):
        txns = [
            _txn("01/04/25", debit=100, narration="A", reference="R1"),
            _txn("02/04/25", debit=200, narration="B", reference="R2"),
        ]
        count = flag_duplicate_transactions(txns)
        assert count == 0
        assert all(t["is_duplicate"] is False for t in txns)

    def test_exact_duplicate_flagged_but_not_removed(self):
        txns = [
            _txn("01/04/25", debit=500, narration="UPI PAYMENT", reference="REF001"),
            _txn("01/04/25", debit=500, narration="UPI PAYMENT", reference="REF001"),
        ]
        count = flag_duplicate_transactions(txns)
        assert count == 1
        assert len(txns) == 2  # nothing removed
        assert txns[0]["is_duplicate"] is False  # first occurrence is the original
        assert txns[1]["is_duplicate"] is True   # second is flagged

    def test_same_amount_different_narration_is_not_a_duplicate(self):
        txns = [
            _txn("01/04/25", debit=500, narration="GROCERY STORE", reference="REF001"),
            _txn("01/04/25", debit=500, narration="FUEL STATION", reference="REF002"),
        ]
        count = flag_duplicate_transactions(txns)
        assert count == 0

    def test_narration_comparison_is_case_insensitive(self):
        txns = [
            _txn("01/04/25", debit=500, narration="upi payment", reference="REF001"),
            _txn("01/04/25", debit=500, narration="UPI PAYMENT", reference="REF001"),
        ]
        count = flag_duplicate_transactions(txns)
        assert count == 1
