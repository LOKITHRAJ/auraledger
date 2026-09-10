import pytest
from parsers.hdfc_pdf_parser import HDFCPDFParser
from parsers.pdf_parser_factory import PDFParserFactory

reportlab = pytest.importorskip("reportlab", reason="reportlab is a test-only dependency for building fixture PDFs")

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape

PAGE_SIZE = landscape(A4)  # 842pt wide -- enough room for 7 well-separated columns

FONT = "Helvetica"
SIZE = 9


def _build_hdfc_pdf(path):
    """
    Builds a synthetic PDF that reproduces the real structural quirks this parser
    exists to handle (discovered against a real HDFC statement):
      1. The "Narration" header label sits well to the right of where narration
         DATA actually starts (which is almost immediately after the Date column) --
         a naive header-position-anchor approach misclassifies Date vs Narration.
      2. Long narrations wrap across multiple physical lines within the table.
      3. Both a debit and a credit transaction, to verify column-span-based
         direction detection (not just "always debit" or nearest-single-point).
      4. A trailing footer/summary section that must NOT be swept into narration.
    No real personal or account data is used anywhere in this fixture.
    """
    c = canvas.Canvas(path, pagesize=PAGE_SIZE)
    c.setFont(FONT, SIZE)
    GAP = 15  # minimum points between adjacent words, comfortably above pdfplumber's word-merge threshold

    def draw(x, y, text):
        c.drawString(x, y, text)
        return x + c.stringWidth(text, FONT, SIZE) + GAP

    # Header row -- Narration label deliberately offset far from where data narration
    # will actually start, exactly like the real quirk this parser works around.
    header_y = 700
    draw(50, header_y, "Date")
    narration_x0 = 250
    draw(narration_x0, header_y, "Narration")
    ref_x0 = 420
    draw(ref_x0, header_y, "Chq./Ref.No.")
    value_dt_x0 = 530
    draw(value_dt_x0, header_y, "ValueDt")
    withdrawal_x0 = 600
    draw(withdrawal_x0, header_y, "WithdrawalAmt.")
    deposit_x0 = 700
    draw(deposit_x0, header_y, "DepositAmt.")
    balance_x0 = 800
    draw(balance_x0, header_y, "ClosingBalance")

    # Transaction 1: single line, debit. Narration starts right after the date
    # (like real HDFC data), NOT at the header's x=250.
    y = 680
    x = draw(50, y, "01/04/25")
    x = draw(x, y, "UPI-GROCERY")
    draw(x, y, "STORE")
    draw(ref_x0, y, "0000000000000001")
    draw(value_dt_x0, y, "01/04/25")
    draw(withdrawal_x0, y, "500.00")
    draw(balance_x0, y, "9500.00")

    # Transaction 2: wraps across two physical lines, credit.
    y = 660
    x = draw(50, y, "02/04/25")
    draw(x, y, "SALARY")
    draw(ref_x0, y, "0000000000000002")
    draw(value_dt_x0, y, "02/04/25")
    draw(deposit_x0, y, "10000.00")
    draw(balance_x0, y, "19500.00")

    y = 645
    draw(60, y, "CREDIT FROM EMPLOYER")

    # Footer/summary block -- must not be absorbed into transaction 2's narration.
    y = 600
    draw(50, y, "STATEMENTSUMMARY :-")
    y = 585
    draw(50, y, "OpeningBalance DrCount CrCount Debits Credits ClosingBal")

    c.save()


@pytest.fixture
def hdfc_pdf_path(tmp_path):
    path = str(tmp_path / "hdfc_statement.pdf")
    _build_hdfc_pdf(path)
    return path


def test_parses_without_error(hdfc_pdf_path):
    parser = HDFCPDFParser()
    df = parser.parse(hdfc_pdf_path)
    assert len(df) == 2


def test_extracts_both_transactions_with_correct_fields(hdfc_pdf_path):
    parser = HDFCPDFParser()
    df = parser.parse(hdfc_pdf_path)

    assert len(df) == 2

    row1 = df.iloc[0]
    assert row1["date"] == "01/04/25"
    assert row1["narration"] == "UPI-GROCERY STORE"
    assert row1["reference"] == "0000000000000001"
    assert row1["debit"] == 500.0
    assert row1["credit"] == 0.0
    assert row1["balance"] == 9500.0

    row2 = df.iloc[1]
    assert row2["date"] == "02/04/25"
    # Narration continuation line must be merged in
    assert row2["narration"] == "SALARY CREDIT FROM EMPLOYER"
    assert row2["reference"] == "0000000000000002"
    assert row2["debit"] == 0.0
    assert row2["credit"] == 10000.0
    assert row2["balance"] == 19500.0


def test_footer_summary_not_absorbed_into_narration(hdfc_pdf_path):
    parser = HDFCPDFParser()
    df = parser.parse(hdfc_pdf_path)
    combined_narrations = " ".join(df["narration"]).upper()
    assert "STATEMENTSUMMARY" not in combined_narrations.replace(" ", "")
    assert "OPENINGBALANCE" not in combined_narrations.replace(" ", "")


def test_no_transaction_table_raises(tmp_path):
    path = str(tmp_path / "no_table.pdf")
    c = canvas.Canvas(path, pagesize=PAGE_SIZE)
    c.setFont(FONT, SIZE)
    c.drawString(50, 700, "Just a letter, no transaction table.")
    c.save()

    parser = HDFCPDFParser()
    from parsers.base_parser import InvalidStatementException
    with pytest.raises(InvalidStatementException):
        parser.parse(path)


class TestBankDetection:
    def _draw_letterhead(self, path, line1, line2="AccountBranch:MainBranchStatementofAccount"):
        # A realistic-length snippet (real statements have far more text than a
        # single short line) -- keeps these tests comfortably above the
        # "usable text layer" length threshold rather than sitting right on it.
        c = canvas.Canvas(path, pagesize=PAGE_SIZE)
        c.setFont(FONT, SIZE)
        c.drawString(50, 700, line1)
        c.drawString(50, 685, line2)
        c.save()

    def test_detects_hdfc_from_dense_unspaced_text(self, tmp_path):
        # Real HDFC PDFs often extract with no space between adjacent tokens
        # (e.g. "HDFCBANKLTD") -- detection must tolerate that.
        path = str(tmp_path / "hdfc_letterhead.pdf")
        self._draw_letterhead(path, "Address:HDFCBANKLTD")
        assert PDFParserFactory.detect_bank(path) == "HDFC BANK"

    def test_hdfc_letterhead_routes_to_dedicated_parser(self, tmp_path):
        path = str(tmp_path / "hdfc_letterhead2.pdf")
        self._draw_letterhead(path, "Address:HDFCBANKLTD")
        parser = PDFParserFactory.get_parser(path)
        assert isinstance(parser, HDFCPDFParser)

    def test_unrecognized_digital_bank_raises_unsupported(self, tmp_path):
        # Product decision: never guess -- a digital PDF (real text layer) whose
        # bank can't be confidently identified must hard-refuse, not silently
        # fall back to generic extraction.
        path = str(tmp_path / "other_bank.pdf")
        self._draw_letterhead(path, "Some Other Cooperative Bank Statement")
        assert PDFParserFactory.detect_bank(path) == "Unsupported / Unidentified"

        from parsers.pdf_parser_factory import UnsupportedPDFBankException
        with pytest.raises(UnsupportedPDFBankException):
            PDFParserFactory.get_parser(path)

    def test_scanned_pdf_uses_generic_ocr_fallback_regardless_of_bank(self, tmp_path):
        # A PDF with no text layer at all (simulated here as a blank page) can't
        # have its bank detected without OCR, and no bank-specific OCR parser
        # exists -- so it must NOT hard-refuse, unlike the digital-PDF case above.
        path = str(tmp_path / "blank_scanned.pdf")
        c = canvas.Canvas(path, pagesize=PAGE_SIZE)
        c.save()  # no drawString calls at all -- no extractable text

        assert PDFParserFactory.detect_bank(path) == "Scanned PDF (OCR)"

        from pdf_reader import PDFReader
        parser = PDFParserFactory.get_parser(path)
        assert isinstance(parser, PDFReader)
