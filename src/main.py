import sys
from pathlib import Path

from config import settings
from excel_reader import ExcelReader
from transaction_builder import TransactionBuilder
from transaction_classifier import TransactionClassifier
from excel_writer import ExcelWriter
from utils import setup_logging

# Setup standard logger
logger = setup_logging()


def main() -> None:
    logger.info("=" * 60)
    logger.info("   AuraLedger - Indian Bank Statement Classification Engine")
    logger.info("=" * 60)

    try:
        # 1. Read Excel file
        reader = ExcelReader()
        df = reader.read_excel()

        # 2. Build transactions from DataFrame
        builder = TransactionBuilder()
        transactions = builder.build_transactions(df)

        if not transactions:
            logger.error("No valid transactions built from the Excel statement. Exiting.")
            sys.exit(1)

        # 3. Initialize ExcelWriter and progressive callback
        writer = ExcelWriter()

        def on_batch_complete(txns):
            writer.write_classified_excel(txns)

        # 4. Classify transactions using AI Classifier (supports progressive updates & PII masking)
        classifier = TransactionClassifier()
        classified_transactions = classifier.classify_transactions(transactions, on_batch_complete=on_batch_complete)

        logger.info("=" * 60)
        logger.info("   Processing completed successfully!")
        logger.info(f"   Classified statement written to: {settings.OUTPUT_FILE}")
        logger.info("=" * 60)

    except Exception as e:
        logger.exception(f"Engine execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()