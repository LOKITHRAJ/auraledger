import logging
from pathlib import Path
import pandas as pd
from parsers.parser_factory import ParserFactory

logger = logging.getLogger("AuraLedger")


class ExcelReader:
    """
    Handles locating the input statement file, delegating parsing to the ParserFactory,
    and returning the standardized transaction DataFrame.
    """

    def get_input_file(self) -> Path:
        """
        Locates the first Excel file in the input directory.
        """
        input_folder = Path("input")
        excel_files = list(input_folder.glob("*.xls*"))

        if not excel_files:
            raise FileNotFoundError("No bank statement Excel file found in the input/ directory.")

        return excel_files[0]

    def read_excel(self, file_path: str = None) -> pd.DataFrame:
        """
        Locates the file (or uses the provided one), resolves the correct bank parser using the factory,
        and parses it into a standardized DataFrame.
        """
        if file_path is None:
            file_path = self.get_input_file()
        else:
            file_path = Path(file_path)

        logger.info(f"Reading bank statement file: {file_path.name}")

        # Retrieve matching parser from factory
        parser = ParserFactory.get_parser(file_path)

        # Parse and return standardized dataframe
        df = parser.parse(file_path)
        
        logger.info(f"Successfully parsed statement. Total rows: {len(df)}")
        return df