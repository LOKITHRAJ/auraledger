import pandas as pd
import pytest
from transaction_builder import TransactionBuilder


@pytest.fixture
def builder():
    return TransactionBuilder()


def test_maps_standard_column_names(builder):
    df = pd.DataFrame({
        "Date": ["01/04/2025"],
        "Narration": ["SALARY CREDIT"],
        "Reference": ["REF001"],
        "Debit": [0],
        "Credit": [50000],
        "Balance": [50000],
    })
    txns = builder.build_transactions(df)
    assert len(txns) == 1
    assert txns[0]["narration"] == "SALARY CREDIT"
    assert txns[0]["credit"] == 50000.0


def test_maps_bank_specific_column_variants(builder):
    # HDFC-style headers
    df = pd.DataFrame({
        "Value Dt": ["01/04/2025"],
        "Particulars": ["ATM WDL"],
        "Chq./Ref.No.": [""],
        "Withdrawal Amt.": [5000],
        "Deposit Amt.": [0],
        "Closing Balance": [45000],
    })
    txns = builder.build_transactions(df)
    assert len(txns) == 1
    assert txns[0]["debit"] == 5000.0
    assert txns[0]["balance"] == 45000.0


def test_missing_required_column_raises(builder):
    df = pd.DataFrame({
        "Date": ["01/04/2025"],
        "Debit": [100],
        "Credit": [0],
        "Balance": [900],
        # no narration/description/particular/remark column at all
    })
    with pytest.raises(ValueError):
        builder.build_transactions(df)


def test_safe_float_handles_dirty_values(builder):
    assert builder._safe_float("1,234.56") == 1234.56
    assert builder._safe_float("") == 0.0
    assert builder._safe_float("-") == 0.0
    assert builder._safe_float("***") == 0.0
    assert builder._safe_float(None) == 0.0
    assert builder._safe_float(float("nan")) == 0.0
    assert builder._safe_float(500) == 500.0


def test_empty_dataframe_returns_empty_list(builder):
    assert builder.build_transactions(pd.DataFrame()) == []
