import re
import logging
from pathlib import Path

from parsers.base_parser import InvalidStatementException

logger = logging.getLogger("AuraLedger")

# Below this many characters of sampled text, treat the PDF as having no usable
# text layer (i.e. scanned/image-only) rather than as "text present but unrecognized".
MIN_TEXT_LENGTH_FOR_BANK_DETECTION = 20


class UnsupportedPDFBankException(InvalidStatementException):
    """
    Raised when a digital (text-layer) PDF's bank could not be confidently
    identified. Deliberately does not apply to scanned PDFs with no text layer
    to inspect -- those still go through the generic OCR extraction path
    regardless of bank, since there is no bank-specific OCR parser to route to.
    """
    pass


class PDFParserFactory:
    """
    Auto-detects the bank from a PDF statement's text content and returns the
    matching bank-specific PDF parser.

    - Digital PDF, bank recognized -> the dedicated parser (e.g. HDFCPDFParser).
    - Digital PDF, bank NOT recognized -> raises UnsupportedPDFBankException
      (never guesses; per product decision, does not silently fall back).
    - Scanned PDF (no text layer to inspect) -> the generic PDFReader (OCR path)
      regardless of bank, since bank detection is impossible without OCR and no
      bank-specific OCR parser exists.

    PDF bank-specific parsers are intentionally separate from the Excel ones in
    `parsers/` -- the same bank's PDF and Excel exports have completely different
    layouts, so there's no meaningful code to share between e.g. `HDFCParser`
    (Excel) and `HDFCPDFParser` (PDF).
    """

    # bank display name -> substring(s) to match in whitespace-stripped, lowercased text
    BANK_SIGNATURES = {
        "HDFC BANK": ("hdfcbank",),
        "STATE BANK OF INDIA": ("statebankofindia",),
        # ICICI's PDF parser is not implemented yet (no real sample statement has
        # been verified against) -- its signature will be added alongside it.
    }

    @classmethod
    def _sample_text(cls, file_path: Path) -> str:
        import pdfplumber
        try:
            with pdfplumber.open(file_path) as pdf:
                text = "".join((page.extract_text() or "") for page in pdf.pages[:2])
        except Exception as e:
            logger.warning(f"Could not sample PDF text for bank detection: {e}")
            return ""
        # Strip all whitespace: some banks' PDF text extraction collapses spacing
        # inconsistently (e.g. "HDFCBANKLTD" with no space at all in places).
        return re.sub(r"\s+", "", text.lower())

    @classmethod
    def _match_bank(cls, normalized_text: str) -> str:
        """Returns the matching bank's display name, or "" if none match."""
        for bank_name, signatures in cls.BANK_SIGNATURES.items():
            if any(sig in normalized_text for sig in signatures):
                return bank_name
        return ""

    @classmethod
    def _parser_for_bank(cls, bank_name: str):
        """Local imports -- keeps parser modules from being loaded until actually needed."""
        from parsers.hdfc_pdf_parser import HDFCPDFParser
        from parsers.sbi_pdf_parser import SBIPDFParser

        return {
            "HDFC BANK": HDFCPDFParser,
            "STATE BANK OF INDIA": SBIPDFParser,
        }.get(bank_name)

    @classmethod
    def get_parser(cls, file_path: Path):
        from pdf_reader import PDFReader  # local import: pdf_reader also uses BaseParser from this package

        file_path = Path(file_path)
        normalized = cls._sample_text(file_path)

        if len(normalized) < MIN_TEXT_LENGTH_FOR_BANK_DETECTION:
            logger.info("No usable text layer (scanned PDF) -- using generic PDFReader (OCR).")
            return PDFReader()

        bank = cls._match_bank(normalized)
        parser_cls = cls._parser_for_bank(bank) if bank else None
        if parser_cls:
            logger.info(f"Auto-detected bank: {bank} (PDF)")
            return parser_cls()

        logger.warning("Digital PDF text sampled but no supported bank signature matched.")
        raise UnsupportedPDFBankException(
            "Unsupported or unidentified bank statement. Please verify the statement format."
        )

    @classmethod
    def detect_bank(cls, file_path: str) -> str:
        """Detects the bank name from the PDF's text content, for display purposes."""
        normalized = cls._sample_text(Path(file_path))
        if len(normalized) < MIN_TEXT_LENGTH_FOR_BANK_DETECTION:
            return "Scanned PDF (OCR)"
        bank = cls._match_bank(normalized)
        return bank or "Unsupported / Unidentified"
