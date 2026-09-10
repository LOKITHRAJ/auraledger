import os
import tempfile
from pathlib import Path

import openpyxl
import pytest
from parsers.parser_factory import ParserFactory
from parsers.hdfc_parser import HDFCParser
from parsers.sbi_parser import SBIParser
from parsers.icici_parser import ICICIParser
from parsers.axis_parser import AxisParser
from parsers.cub_parser import CUBParser
from parsers.generic_parser import GenericParser


def _make_xlsx(rows):
    """Writes rows to a temp .xlsx file and returns its Path. Caller must clean up."""
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)
    return Path(path)


@pytest.fixture
def cleanup_paths():
    paths = []
    yield paths
    for p in paths:
        if p.exists():
            p.unlink()


@pytest.mark.parametrize("letterhead,expected_parser", [
    ("HDFC BANK LIMITED", HDFCParser),
    ("STATE BANK OF INDIA", SBIParser),
    ("ICICI Bank Limited", ICICIParser),
    ("Axis Bank Ltd", AxisParser),
    ("City Union Bank Ltd", CUBParser),
])
def test_detects_bank_from_letterhead_text(cleanup_paths, letterhead, expected_parser):
    path = _make_xlsx([[letterhead], ["Statement"], []])
    cleanup_paths.append(path)
    parser = ParserFactory.get_parser(path)
    assert isinstance(parser, expected_parser)


def test_unrecognized_bank_falls_back_to_generic_parser(cleanup_paths):
    path = _make_xlsx([["Some Cooperative Bank Nobody Coded a Parser For"], []])
    cleanup_paths.append(path)
    parser = ParserFactory.get_parser(path)
    assert isinstance(parser, GenericParser)


def test_csv_always_routes_to_generic_parser(cleanup_paths):
    fd, path_str = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    path = Path(path_str)
    path.write_text("Date,Narration,Debit,Credit,Balance\n01-04-2025,TEST,100,0,900\n")
    cleanup_paths.append(path)
    parser = ParserFactory.get_parser(path)
    assert isinstance(parser, GenericParser)


def test_filename_fallback_detection_when_no_letterhead_text(cleanup_paths):
    # No recognizable bank text in the content, but "hdfc" appears in the filename
    fd, path_str = tempfile.mkstemp(suffix="_hdfc_export.xlsx")
    os.close(fd)
    path = Path(path_str)
    wb = openpyxl.Workbook()
    wb.active.append(["No bank name here at all"])
    wb.save(path)
    cleanup_paths.append(path)
    parser = ParserFactory.get_parser(path)
    assert isinstance(parser, HDFCParser)


def test_detect_bank_returns_friendly_names(cleanup_paths):
    path = _make_xlsx([["HDFC BANK LIMITED"], []])
    cleanup_paths.append(path)
    assert ParserFactory.detect_bank(str(path)) == "HDFC BANK"
