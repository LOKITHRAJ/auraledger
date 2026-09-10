import pytest
from pii_anonymizer import PIIAnonymizer


@pytest.fixture
def anon():
    return PIIAnonymizer()


def test_masks_upi_id(anon):
    result = anon.anonymize_narration("Paid via john.doe@okicici for groceries")
    assert "[UPI]" in result
    assert "john.doe@okicici" not in result


def test_masks_ifsc_code(anon):
    result = anon.anonymize_narration("NEFT to SBIN0012798 branch")
    assert "[IFSC]" in result
    assert "SBIN0012798" not in result


def test_masks_mobile_number(anon):
    result = anon.anonymize_narration("Registered mobile 9876543210 for alerts")
    assert "[PHONE]" in result
    assert "9876543210" not in result


def test_masks_reference_number(anon):
    result = anon.anonymize_narration("IMPS ref 102390687594 completed")
    assert "[REF]" in result
    assert "102390687594" not in result


def test_masks_account_number(anon):
    result = anon.anonymize_narration("Transfer to account XXXXXXXXXXX9673")
    assert "[NUM]" in result
    assert "XXXXXXXXXXX9673" not in result


@pytest.mark.parametrize("narration", [
    "UPI Payment to ROYAL BAKERY AND SWE",
    "UPI Payment to SOWMYA  S",
    "UPI Payment to MR LOKITHRAJ R",
])
def test_masks_personal_name_after_lowercase_to(anon, narration):
    # Regression test: preprocessor emits lowercase "to"/"from" connectors,
    # but the original regex only matched uppercase keywords -- found and fixed in Day 1.
    result = anon.anonymize_narration(narration)
    assert "[NAME]" in result


@pytest.mark.parametrize("narration", [
    "UPI Receipt from MR LOKITHRAJ R",
    "UPI Receipt from SOWMYA S",
    "UPI Receipt from RAVI LOKITHRAJ",
])
def test_masks_personal_name_after_from(anon, narration):
    # Regression test: the original pattern had no standalone "FROM" keyword,
    # so credit-side transactions leaked the sender's name entirely -- found and fixed in Day 1.
    result = anon.anonymize_narration(narration)
    assert "[NAME]" in result


@pytest.mark.parametrize("narration", [
    "UPI Payment to AMAZON SELLER SERVIC",
    "UPI Payment to AIRTEL",
    "UPI Payment to DNV FUEL STATION",
])
def test_does_not_mask_known_merchant_names(anon, narration):
    # Merchant/business names are intentionally not treated as PII -- only individuals are.
    result = anon.anonymize_narration(narration)
    assert "[NAME]" not in result


def test_empty_and_none_narration_returns_empty_string(anon):
    assert anon.anonymize_narration("") == ""
    assert anon.anonymize_narration(None) == ""


def test_anonymize_transactions_only_touches_narration_field(anon):
    txns = [{"narration": "Paid to john@okicici", "debit": 500.0, "credit": 0.0}]
    result = anon.anonymize_transactions(txns)
    assert result[0]["narration"] != txns[0]["narration"]
    assert result[0]["debit"] == 500.0
    # Original list must not be mutated
    assert txns[0]["narration"] == "Paid to john@okicici"
