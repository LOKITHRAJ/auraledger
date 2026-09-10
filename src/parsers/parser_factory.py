import logging
from pathlib import Path
import pandas as pd

from parsers.base_parser import BaseParser, InvalidStatementException
from parsers.hdfc_parser import HDFCParser
from parsers.sbi_parser import SBIParser
from parsers.icici_parser import ICICIParser
from parsers.axis_parser import AxisParser
from parsers.cub_parser import CUBParser
from parsers.generic_parser import GenericParser

logger = logging.getLogger("AuraLedger")


class ParserFactory:
    """
    Factory to auto-detect bank from the first 30 rows of a spreadsheet
    and return the corresponding parser instance.
    """

    @classmethod
    def get_parser(cls, file_path: Path) -> BaseParser:
        logger.info(f"Auto-detecting bank parser for statement: {file_path}")

        # CSV exports rarely carry bank letterhead/metadata rows, so route straight
        # to the generic dynamic-column-mapping parser instead of trying bank detection.
        if file_path.suffix.lower() == ".csv":
            logger.info("CSV file detected — using GenericParser.")
            return GenericParser()

        try:
            # Read first 30 rows to inspect metadata
            preview = pd.read_excel(file_path, header=None, nrows=30, dtype=str)
        except Exception as e:
            logger.error(f"Failed to read preview rows: {e}")
            raise InvalidStatementException(f"Error reading file preview: {e}")

        # Combine all cells to one lowercase block of text
        full_text = " ".join(
            preview.fillna("").astype(str).values.flatten()
        ).lower()

        # Detection logic
        if "hdfc bank" in full_text:
            logger.info("Auto-detected bank: HDFC BANK")
            return HDFCParser()
        elif "state bank of india" in full_text:
            logger.info("Auto-detected bank: STATE BANK OF INDIA")
            return SBIParser()
        elif "icici bank" in full_text:
            logger.info("Auto-detected bank: ICICI BANK")
            return ICICIParser()
        elif "axis bank" in full_text:
            logger.info("Auto-detected bank: AXIS BANK")
            return AxisParser()
        elif "city union bank" in full_text or "ciub0000" in full_text:
            logger.info("Auto-detected bank: CITY UNION BANK")
            return CUBParser()

        # Fallback to keyword-based detection on filenames
        filename_lower = file_path.name.lower()
        if "hdfc" in filename_lower:
            logger.warning("No header metadata match. Fallback detection from filename: HDFC BANK")
            return HDFCParser()
        elif "sbi" in filename_lower:
            logger.warning("No header metadata match. Fallback detection from filename: STATE BANK OF INDIA")
            return SBIParser()
        elif "icici" in filename_lower:
            logger.warning("No header metadata match. Fallback detection from filename: ICICI BANK")
            return ICICIParser()
        elif "axis" in filename_lower:
            logger.warning("No header metadata match. Fallback detection from filename: AXIS BANK")
            return AxisParser()
        elif "cub" in filename_lower or "cityunion" in filename_lower:
            logger.warning("No header metadata match. Fallback detection from filename: CITY UNION BANK")
            return CUBParser()

        # No known bank signature matched — fall back to best-effort generic parsing
        # instead of hard-failing, so an unrecognized bank can still be processed.
        logger.warning(
            f"No matching bank signature for {file_path.name}. Falling back to GenericParser."
        )
        return GenericParser()

    @classmethod
    def detect_bank(cls, file_path: str) -> str:
        """
        Detects the bank name from the file content or name.
        """
        try:
            parser = cls.get_parser(Path(file_path))
            name = parser.__class__.__name__.replace("Parser", "")
            if name == "HDFC":
                return "HDFC BANK"
            elif name == "SBI":
                return "STATE BANK OF INDIA"
            elif name == "ICICI":
                return "ICICI BANK"
            elif name == "Axis":
                return "AXIS BANK"
            elif name == "CUB":
                return "CITY UNION BANK"
            elif name == "Generic":
                return "Other / Auto-Detected"
            return name.upper()
        except Exception as e:
            logger.error(f"Error detecting bank name: {e}")
            return "Unknown Bank"
