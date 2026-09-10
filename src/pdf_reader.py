import re
import logging
from pathlib import Path
from typing import List

import pandas as pd

from parsers.base_parser import BaseParser, InvalidStatementException

logger = logging.getLogger("AuraLedger")


class InvalidPDFException(InvalidStatementException):
    """Raised when a PDF cannot be parsed into a transaction table, digitally or via OCR."""
    pass


class PDFReader(BaseParser):
    """
    Extracts standardized bank statement transactions from PDF files.

    Tries digital (text-layer) table extraction first via pdfplumber -- fast and
    accurate for normal downloaded statements. Falls back to OCR (pytesseract +
    pdf2image) for scanned/image-only PDFs where no text layer is present.
    """

    HEADER_SCAN_ROWS = 30
    HEADER_KEYWORDS = [
        "date", "narration", "particulars", "description", "remarks",
        "debit", "credit", "withdrawal", "deposit", "balance"
    ]
    COLUMN_PATTERNS = {
        "date": ["date", "value date", "txn date", "transaction date"],
        "narration": ["narration", "particulars", "description", "remarks", "details"],
        "reference": ["chq./ref.no.", "chq no", "ref no", "reference", "cheque no", "utr"],
        "debit": ["withdrawal amt.", "debit", "withdrawal", "dr"],
        "credit": ["deposit amt.", "credit", "deposit", "cr"],
        "balance": ["closing balance", "balance", "bal", "running balance"]
    }

    def __init__(self) -> None:
        from config import settings
        self.tesseract_cmd = getattr(settings, "TESSERACT_CMD", "") or None
        self.poppler_path = getattr(settings, "POPPLER_PATH", "") or None

    def parse(self, file_path: Path) -> pd.DataFrame:
        import pdfplumber

        file_path = Path(file_path)
        logger.info(f"Parsing PDF statement: {file_path}")

        try:
            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
        except Exception:
            page_count = 0

        has_text = self._has_text_layer(file_path)
        if has_text:
            logger.info("Digital PDF detected (text layer present). Using pdfplumber table extraction.")
            rows = self._extract_rows_digital(file_path)
            ocr_used = False
            extraction_method = "digital_table"
        else:
            logger.info("No text layer detected -- falling back to OCR (pytesseract).")
            rows = self._extract_rows_ocr(file_path)
            ocr_used = True
            extraction_method = "ocr"

        # Readable by the caller after parse() returns.
        self.extraction_info = {
            "extraction_method": extraction_method,
            "page_count": page_count,
            "text_available": has_text,
            "table_available": bool(rows) if has_text else None,
            "ocr_used": ocr_used,
        }

        if not rows:
            raise InvalidPDFException(
                "No transaction rows could be extracted from this PDF. "
                "It may not contain a structured statement table."
            )

        df = self._rows_to_standard_columns(rows)
        return self.common_cleanup(df)

    def _has_text_layer(self, file_path: Path) -> bool:
        import pdfplumber
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages[:3]:
                    text = page.extract_text() or ""
                    if len(text.strip()) > 20:
                        return True
        except Exception as e:
            logger.warning(f"Failed to inspect PDF text layer, assuming scanned: {e}")
            return False
        return False

    def _extract_rows_digital(self, file_path: Path) -> List[List[str]]:
        import pdfplumber
        all_rows = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables():
                        all_rows.extend(table)
        except Exception as e:
            raise InvalidPDFException(f"Error reading PDF: {e}")
        return all_rows

    def _extract_rows_ocr(self, file_path: Path) -> List[List[str]]:
        import pytesseract
        from pytesseract import Output
        from pdf2image import convert_from_path

        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

        convert_kwargs = {"poppler_path": self.poppler_path} if self.poppler_path else {}

        try:
            images = convert_from_path(str(file_path), **convert_kwargs)
        except Exception as e:
            raise InvalidPDFException(f"Could not render PDF pages for OCR: {e}")

        # Word-level rows, y-clustered per page (NOT plain image_to_string: Tesseract's default
        # block segmentation reads column-by-column for tabular scans, which scrambles row order).
        word_rows: List[List[dict]] = []
        for page_num, image in enumerate(images, 1):
            try:
                data = pytesseract.image_to_data(image, output_type=Output.DICT)
            except Exception as e:
                raise InvalidPDFException(f"OCR failed on page {page_num}: {e}")
            word_rows.extend(self._cluster_words_into_rows(data))

        if not word_rows:
            return []

        # Reconstruct column boundaries from consistently empty vertical gaps -- but
        # only across table rows (header onward). Free-flowing preamble text (e.g. a
        # bank name title) doesn't follow the column grid and can span exactly the gap
        # a real column boundary would occupy, so it must be excluded from detection.
        header_idx = -1
        for idx, row in enumerate(word_rows[: self.HEADER_SCAN_ROWS]):
            row_text = " ".join(w["text"] for w in row).lower()
            if sum(1 for kw in self.HEADER_KEYWORDS if kw in row_text) >= 3:
                header_idx = idx
                break
        table_rows = word_rows[header_idx:] if header_idx != -1 else word_rows

        boundaries = self._detect_column_boundaries(table_rows)
        if not boundaries:
            return []

        return [self._bucket_words_by_boundaries(row, boundaries) for row in word_rows]

    def _cluster_words_into_rows(self, ocr_data: dict) -> List[List[dict]]:
        """
        Groups OCR word boxes into table rows by y-coordinate proximity, sorted
        left-to-right within each row -- independent of Tesseract's own block/line grouping.
        """
        words = []
        for i in range(len(ocr_data["text"])):
            text = ocr_data["text"][i].strip()
            if not text:
                continue
            words.append({
                "text": text,
                "left": ocr_data["left"][i],
                "top": ocr_data["top"][i],
                "width": ocr_data["width"][i],
                "height": ocr_data["height"][i],
            })

        if not words:
            return []

        words.sort(key=lambda w: w["top"])
        avg_height = sum(w["height"] for w in words) / len(words)
        row_tolerance = max(10, int(avg_height * 0.6))

        rows = []
        current_row = [words[0]]
        current_top = words[0]["top"]
        for w in words[1:]:
            if abs(w["top"] - current_top) <= row_tolerance:
                current_row.append(w)
            else:
                current_row.sort(key=lambda x: x["left"])
                rows.append(current_row)
                current_row = [w]
                current_top = w["top"]
        current_row.sort(key=lambda x: x["left"])
        rows.append(current_row)
        return rows

    def _detect_column_boundaries(self, word_rows: List[List[dict]], min_gap_width: int = 15) -> List[int]:
        """
        Finds x-axis column boundaries by locating wide, consistently empty vertical
        bands across every OCR'd row on the page. This is what actually separates
        columns visually in the source scan, and is far more reliable than trying to
        infer boundaries from the header row's word positions alone.
        """
        all_words = [w for row in word_rows for w in row]
        if not all_words:
            return []

        max_x = max(w["left"] + w["width"] for w in all_words) + 20
        covered = bytearray(max_x + 1)
        for w in all_words:
            start = max(0, w["left"] - 2)
            end = min(max_x, w["left"] + w["width"] + 2)
            for x in range(start, end):
                covered[x] = 1

        gaps = []
        gap_start = None
        for x in range(max_x):
            if not covered[x]:
                if gap_start is None:
                    gap_start = x
            elif gap_start is not None:
                gaps.append((gap_start, x))
                gap_start = None
        if gap_start is not None:
            gaps.append((gap_start, max_x))

        wide_gaps = [g for g in gaps if (g[1] - g[0]) >= min_gap_width]
        return sorted((g[0] + g[1]) // 2 for g in wide_gaps)

    def _bucket_words_by_boundaries(self, row_words: List[dict], boundaries: List[int]) -> List[str]:
        """
        Splits a row's words into columns using the detected boundary cut-points,
        joining words that fall in the same column into that column's cell text.
        """
        columns = [[] for _ in range(len(boundaries) + 1)]
        for w in row_words:
            col_idx = sum(1 for b in boundaries if w["left"] >= b)
            columns[col_idx].append(w["text"])
        return [" ".join(c) for c in columns]

    def _find_header_row_index(self, rows: List[List[str]]) -> int:
        for idx, row in enumerate(rows[: self.HEADER_SCAN_ROWS]):
            row_text = " ".join(str(c or "") for c in row).lower()
            score = sum(1 for kw in self.HEADER_KEYWORDS if kw in row_text)
            if score >= 3:
                return idx
        return -1

    def _rows_to_standard_columns(self, rows: List[List[str]]) -> pd.DataFrame:
        header_idx = self._find_header_row_index(rows)
        if header_idx == -1:
            raise InvalidPDFException(
                "Could not detect a transaction table (Date/Narration/Debit/Credit columns) in this PDF."
            )

        header = [str(c or "").strip() for c in rows[header_idx]]
        # Guard against blank/duplicate header cells (e.g. an empty edge bucket from
        # column-boundary detection) -- pandas allows duplicate column names at
        # construction, but that later breaks single-column selection (df[col].dtype).
        seen = {}
        for i, h in enumerate(header):
            key = h if h else "_blank"
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > 1 or not h:
                header[i] = f"{key}_{seen[key]}"

        data_rows = rows[header_idx + 1:]

        # Normalize ragged row lengths (common with pdfplumber/OCR extraction) to the header width
        normalized = []
        for row in data_rows:
            row = list(row)
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))
            else:
                row = row[: len(header)]
            normalized.append(row)

        df = pd.DataFrame(normalized, columns=header)
        df_cols = [str(c).strip() for c in df.columns]

        mapped_columns = {}
        claimed_cols = set()
        for std_key, patterns in self.COLUMN_PATTERNS.items():
            matched_col = None
            for col in df_cols:
                if col in claimed_cols:
                    continue
                if col.lower() in [p.lower() for p in patterns]:
                    matched_col = col
                    break
            if not matched_col:
                for col in df_cols:
                    if col in claimed_cols:
                        continue
                    if any(p in col.lower() for p in patterns):
                        matched_col = col
                        break
            if matched_col:
                mapped_columns[std_key] = matched_col
                claimed_cols.add(matched_col)
            elif std_key in ("date", "narration"):
                raise InvalidPDFException(
                    f"Required column not found for '{std_key}'. Detected columns: {df_cols}"
                )

        return df.rename(columns={v: k for k, v in mapped_columns.items()})
