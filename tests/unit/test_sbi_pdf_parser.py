import pytest
from parsers.sbi_pdf_parser import SBIPDFParser
from parsers.pdf_parser_factory import PDFParserFactory

reportlab = pytest.importorskip("reportlab", reason="reportlab is a test-only dependency for building fixture PDFs")

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

FONT = "Helvetica"
SIZE = 9


def _build_sbi_pdf(path, letterhead=True):
    """
    Reproduces SBI's real structural quirks (discovered against a real
    statement, not guessed):
      1. No reliably text-extractable header row -- only a stray "Balance"
         fragment survives, so table-start detection can't be keyword-based.
      2. The transaction TYPE ("WDL TFR"/"DEP TFR") sits on its own line
         immediately BEFORE the date line -- the opposite order from HDFC.
      3. The date line already carries both dates, narration-start, and all
         four trailing fields (Ref No, Debit, Credit, Balance) space-separated,
         with "-" as an explicit placeholder for the empty one of Debit/Credit
         -- direction is unambiguous from content, unlike HDFC.
      4. Narration continues across further lines with no other fields.
    No real personal or account data is used anywhere in this fixture.
    """
    c = canvas.Canvas(path, pagesize=A4)
    c.setFont(FONT, SIZE)

    def draw(x, y, text):
        c.drawString(x, y, text)

    y = 750
    if letterhead:
        draw(50, y, "State Bank of India")
        y -= 40
        draw(50, y, "Balance")  # the one surviving header fragment, like the real file
        y -= 20

    # Transaction 1: debit, single continuation line
    draw(50, y, "WDL TFR")
    y -= 15
    draw(50, y, "01/08/2026 01/08/2026 UPI/DR/123456789012/TESTMERCHANT - 500.00 - 9500.00")
    y -= 15
    draw(50, y, "YESB/testqr1/UPI")
    y -= 15
    draw(50, y, "0099999999999 AT 00862")
    y -= 15
    draw(50, y, "TESTCITY")
    y -= 20

    # Transaction 2: credit, no continuation lines at all
    draw(50, y, "DEP TFR")
    y -= 15
    draw(50, y, "02/08/2026 02/08/2026 UPI/CR/987654321098/SALARYCO - - 20000.00 29500.00")
    y -= 20

    # Transaction 3: ATM withdrawal type, multi-line narration
    draw(50, y, "ATM WDL")
    y -= 15
    draw(50, y, "03/08/2026 03/08/2026 ATM CASH 555000111222 VIP Nagar - 2000.00 - 27500.00")
    y -= 15
    draw(50, y, "SomeBranchName")
    y -= 25

    draw(50, y, "Page no. 1")

    c.save()


@pytest.fixture
def sbi_pdf_path(tmp_path):
    path = str(tmp_path / "sbi_statement.pdf")
    _build_sbi_pdf(path)
    return path


def test_extracts_all_transactions_with_correct_fields(sbi_pdf_path):
    parser = SBIPDFParser()
    df = parser.parse(sbi_pdf_path)

    assert len(df) == 3

    row1 = df.iloc[0]
    assert row1["date"] == "01/08/2026"
    assert row1["narration"] == "WDL TFR UPI/DR/123456789012/TESTMERCHANT YESB/testqr1/UPI 0099999999999 AT 00862 TESTCITY"
    assert row1["debit"] == 500.0
    assert row1["credit"] == 0.0
    assert row1["balance"] == 9500.0

    row2 = df.iloc[1]
    assert row2["date"] == "02/08/2026"
    assert row2["narration"] == "DEP TFR UPI/CR/987654321098/SALARYCO"
    assert row2["debit"] == 0.0
    assert row2["credit"] == 20000.0
    assert row2["balance"] == 29500.0

    row3 = df.iloc[2]
    assert "ATM WDL" in row3["narration"]
    assert "SomeBranchName" in row3["narration"]
    assert row3["debit"] == 2000.0
    assert row3["credit"] == 0.0
    assert row3["balance"] == 27500.0


def test_page_footer_not_absorbed_into_last_transaction(sbi_pdf_path):
    parser = SBIPDFParser()
    df = parser.parse(sbi_pdf_path)
    combined = " ".join(df["narration"]).upper().replace(" ", "")
    assert "PAGENO" not in combined


def test_no_transaction_table_raises(tmp_path):
    path = str(tmp_path / "no_table.pdf")
    c = canvas.Canvas(path, pagesize=A4)
    c.setFont(FONT, SIZE)
    c.drawString(50, 700, "Just some unrelated text, no dates here at all.")
    c.save()

    parser = SBIPDFParser()
    from parsers.base_parser import InvalidStatementException
    with pytest.raises(InvalidStatementException):
        parser.parse(path)


class TestBankDetection:
    def test_detects_sbi_and_routes_to_dedicated_parser(self, tmp_path):
        path = str(tmp_path / "sbi_letterhead.pdf")
        c = canvas.Canvas(path, pagesize=A4)
        c.setFont(FONT, SIZE)
        c.drawString(50, 700, "State Bank of India")
        c.drawString(50, 685, "STATEMENT OF ACCOUNT for the period requested by the customer")
        c.save()

        assert PDFParserFactory.detect_bank(path) == "STATE BANK OF INDIA"
        parser = PDFParserFactory.get_parser(path)
        assert isinstance(parser, SBIPDFParser)
