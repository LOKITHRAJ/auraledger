from pathlib import Path

ALLOWED_EXTENSIONS = {".xls", ".xlsx", ".csv", ".pdf"}
MAX_FILE_SIZE_MB = 25
MAX_PDF_PAGES = 200


class FileValidationError(Exception):
    """Raised when an uploaded statement file fails pre-parse validation."""
    pass


def validate_extension(filename: str) -> str:
    """
    Validates the file extension is supported. Returns the lowercase extension.
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Unsupported file type '{ext or 'unknown'}'. Please upload a .xls, .xlsx, .csv, or .pdf bank statement."
        )
    return ext


def validate_size(size_bytes: int, filename: str) -> None:
    """
    Validates the file is neither empty nor larger than the configured limit.
    """
    if size_bytes <= 0:
        raise FileValidationError(f"'{filename}' is empty (0 bytes). Please upload a valid statement file.")

    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        size_mb = size_bytes / (1024 * 1024)
        raise FileValidationError(
            f"'{filename}' is {size_mb:.1f} MB, which exceeds the {MAX_FILE_SIZE_MB} MB limit."
        )


def validate_readable(file_path: str, ext: str) -> None:
    """
    Attempts a lightweight open of the file to catch password-protected or corrupted
    files before they reach the full parsing pipeline, with a user-friendly error message.
    """
    filename = Path(file_path).name

    try:
        if ext == ".csv":
            import pandas as pd
            pd.read_csv(file_path, nrows=5)

        elif ext == ".xlsx":
            import zipfile
            if not zipfile.is_zipfile(file_path):
                # Encrypted/password-protected .xlsx files are OLE containers, not zip archives
                raise FileValidationError(
                    f"'{filename}' appears to be password-protected or corrupted. "
                    "Please remove the password and re-upload."
                )
            import openpyxl
            wb = openpyxl.load_workbook(file_path, read_only=True)
            wb.close()

        elif ext == ".xls":
            import xlrd
            xlrd.open_workbook(file_path)

        elif ext == ".pdf":
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                if page_count == 0:
                    raise FileValidationError(f"'{filename}' has no pages.")
                if page_count > MAX_PDF_PAGES:
                    raise FileValidationError(
                        f"'{filename}' has {page_count} pages, which exceeds the {MAX_PDF_PAGES}-page limit."
                    )

    except FileValidationError:
        raise
    except Exception as e:
        # Some libraries (e.g. pdfplumber/pdfminer for encrypted PDFs) wrap the real
        # cause in .args without including it in str(e), so search those too.
        msg = " ".join([str(e), repr(e.args), type(e).__name__]).lower()
        if "password" in msg or "encrypt" in msg:
            raise FileValidationError(
                f"'{filename}' is password-protected. Please remove the password and re-upload."
            )
        raise FileValidationError(
            f"'{filename}' could not be read — it may be corrupted or in an unsupported format. ({e})"
        )


def validate_statement_file(filename: str, size_bytes: int, file_path: str) -> str:
    """
    Runs all pre-parse validation checks on an uploaded statement file.
    Returns the validated file extension. Raises FileValidationError with a
    user-friendly message on any failure.
    """
    ext = validate_extension(filename)
    validate_size(size_bytes, filename)
    validate_readable(file_path, ext)
    return ext
