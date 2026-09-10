import pytest
from preprocessor import TransactionPreprocessor


@pytest.fixture
def pre():
    return TransactionPreprocessor()


@pytest.mark.parametrize("narration,debit,credit,expected_category", [
    ("SMS CHARGES FOR QTR APR-JUN", 50.0, 0.0, "Bank Charges"),
    ("AMB CHARGE NON MAINTENANCE OF MIN BAL", 590.0, 0.0, "Bank Charges"),
    ("GST ON SMS CHARGES", 9.0, 0.0, "Taxes"),
    ("CGST ON BANK CHARGES", 4.5, 0.0, "Taxes"),
    ("INTEREST CREDIT FOR THE QUARTER", 0.0, 1200.0, "Interest Income"),
    ("SB INT PAID", 0.0, 45.0, "Interest Income"),
    ("ATM WDL CASH NWD MG ROAD BRANCH", 5000.0, 0.0, "Cash Withdrawal"),
    ("NWD/ATM/1234/BRANCH", 2000.0, 0.0, "Cash Withdrawal"),
])
def test_keyword_rule_matches_expected_category(pre, narration, debit, credit, expected_category):
    result = pre.apply_keyword_rules(narration, debit, credit)
    assert result is not None
    assert result["category"] == expected_category


def test_gst_takes_precedence_over_generic_bank_charges_keyword(pre):
    # Regression test (Day 3): "GST ON SMS CHARGES" was matching the Bank Charges rule
    # first because "SMS CHARGE" is also a Bank Charges keyword. GST should win.
    result = pre.apply_keyword_rules("GST ON SMS CHARGES", 9.0, 0.0)
    assert result["category"] == "Taxes"


def test_no_rule_matches_ordinary_merchant_payment(pre):
    result = pre.apply_keyword_rules("UPI-SOME RANDOM MERCHANT-abc@ok", 500.0, 0.0)
    assert result is None


def test_interest_rule_only_applies_on_credit_side(pre):
    # "INTEREST" keywords are scoped to credit-direction only -- a debit shouldn't match
    result = pre.apply_keyword_rules("SB INT PAID", 45.0, 0.0)
    assert result is None


def test_preprocess_flags_small_value_transactions_as_miscellaneous(pre):
    txns = [{"narration": "SOME RANDOM SMALL PAYMENT", "debit": 50.0, "credit": 0.0, "balance": 100.0, "date": "2025-04-01"}]
    result = pre.preprocess(txns)
    assert result[0]["category"] == "Miscellaneous"
    assert result[0]["requires_ai"] is False
    assert result[0]["confidence"] == 100


def test_preprocess_flags_large_unmatched_transactions_for_ai(pre):
    txns = [{"narration": "UPI-BIG MERCHANT PAYMENT-abc@ok", "debit": 50000.0, "credit": 0.0, "balance": 100.0, "date": "2025-04-01"}]
    result = pre.preprocess(txns)
    assert result[0]["requires_ai"] is True


def test_preprocess_extracts_upi_counterparty(pre):
    txns = [{"narration": "UPI-JOHN DOE-john@okicici-102390687594-UPI", "debit": 5000.0, "credit": 0.0, "balance": 100.0, "date": "2025-04-01"}]
    result = pre.preprocess(txns)
    assert "JOHN DOE" in result[0]["normalized_narration"]
