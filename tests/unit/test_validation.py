import os
import tempfile

import pytest
from services.validation import validate_statement_file, FileValidationError


def _write_temp(filename, content=b""):
    path = os.path.join(tempfile.gettempdir(), filename)
    with open(path, "wb") as f:
        f.write(content)
    return path


def test_rejects_unsupported_extension():
    with pytest.raises(FileValidationError, match="Unsupported file type"):
        validate_statement_file("statement.docx", 1000, "irrelevant_path.docx")


def test_rejects_zero_byte_file():
    path = _write_temp("empty_test.xlsx", b"")
    try:
        with pytest.raises(FileValidationError, match="empty"):
            validate_statement_file("empty_test.xlsx", 0, path)
    finally:
        os.remove(path)


def test_rejects_oversized_file():
    path = _write_temp("oversized_test.xlsx", b"0" * 100)
    try:
        with pytest.raises(FileValidationError, match="exceeds"):
            validate_statement_file("oversized_test.xlsx", 26 * 1024 * 1024, path)
    finally:
        os.remove(path)


def test_rejects_corrupted_or_password_protected_xlsx():
    path = _write_temp("corrupted_test.xlsx", b"NOT A REAL XLSX FILE CONTENT")
    try:
        with pytest.raises(FileValidationError, match="password-protected or corrupted"):
            validate_statement_file("corrupted_test.xlsx", 30, path)
    finally:
        os.remove(path)


def test_accepts_valid_real_statement_file():
    real_file = os.path.join(
        os.path.dirname(__file__), "..", "..", "input", "excel", "BankStatement_HDFC.xls"
    )
    if not os.path.exists(real_file):
        pytest.skip("Sample statement not present in input/excel/")
    ext = validate_statement_file(
        "BankStatement_HDFC.xls", os.path.getsize(real_file), real_file
    )
    assert ext == ".xls"
