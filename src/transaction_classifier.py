import logging
from typing import List, Dict, Any, Callable

from pii_anonymizer import PIIAnonymizer
from ai_client import get_ai_client, BaseAIClient

logger = logging.getLogger("AuraLedger")


class TransactionClassifier:
    """
    Business logic layer that maps and classifies transactions.
    Extracts unique transaction types in-memory for the current run,
    classifies them via the AI Client, and maps the results back.
    """

    def __init__(self, ai_client: BaseAIClient = None) -> None:
        from config import settings
        from preprocessor import TransactionPreprocessor
        self.batch_size = settings.BATCH_SIZE
        self.anonymizer = PIIAnonymizer()
        self.ai_client = ai_client or get_ai_client()
        self.preprocessor = TransactionPreprocessor()

    def _generate_key(self, normalized_narration: str, debit: float) -> str:
        """
        Generates a key combining normalized narration with transaction type (debit/credit)
        to distinguish identical narrations that behave differently.
        """
        txn_type = "debit" if debit > 0 else "credit"
        return f"{normalized_narration}||{txn_type}"

    def classify_transactions(self, transactions: List[Dict[str, Any]], on_batch_complete: Callable[[List[Dict[str, Any]]], None] = None) -> List[Dict[str, Any]]:
        """
        Classifies bank transactions by first running them through the Pre-Processing Engine.
        Only sends transactions requiring AI to the AI Client, using their normalized narrations.
        Merges results back into the original transactions.
        """
        if not transactions:
            logger.warning("No transactions provided for classification.")
            return []

        logger.info(f"Starting classification process for {len(transactions)} transactions.")

        # 1. Run Preprocessor
        classified_transactions = self.preprocessor.preprocess(transactions)

        # Trigger callback for initial state
        if on_batch_complete:
            on_batch_complete(classified_transactions)

        # 2. Group transactions requiring AI by unique templates in-memory
        unique_keys = {}  # key -> representative transaction dict

        for txn in classified_transactions:
            if not txn.get("requires_ai", True):
                continue

            norm_narration = txn.get("normalized_narration", "")
            key = self._generate_key(norm_narration, txn.get("debit", 0.0))

            if key not in unique_keys:
                unique_keys[key] = {
                    "date": txn.get("date", ""),
                    "narration": self.anonymizer.anonymize_narration(norm_narration),  # PII-masked on top of normalization before it ever reaches the AI
                    "debit": txn.get("debit", 0.0),
                    "credit": txn.get("credit", 0.0),
                    "balance": txn.get("balance", 0.0)
                }

        # 3. Classify unique keys in batches of BATCH_SIZE
        keys_list = list(unique_keys.keys())
        total_unique = len(keys_list)
        representative_list = [unique_keys[k] for k in keys_list]
        
        logger.info(f"Identified {total_unique} unique transaction types requiring AI in this statement.")
        
        classifications = {}  # key -> AI result dict

        for i in range(0, total_unique, self.batch_size):
            batch_txns = representative_list[i : i + self.batch_size]
            batch_keys = keys_list[i : i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (total_unique + self.batch_size - 1) // self.batch_size

            logger.info(f"Sending batch {batch_num}/{total_batches} ({len(batch_txns)} unique items) to AI...")

            try:
                classified_batch = self.ai_client.classify_batch(batch_txns)
                
                if len(classified_batch) != len(batch_txns):
                    raise ValueError(
                        f"AI returned {len(classified_batch)} items, expected {len(batch_txns)}."
                    )

                # Store result
                for key, result in zip(batch_keys, classified_batch):
                    classifications[key] = {
                        "category": result.get("category", "Review Narration"),
                        "nature": result.get("nature", "Unknown"),
                        "description": result.get("description", ""),
                        "confidence": result.get("confidence", 0)
                    }

            except Exception as e:
                logger.error(f"Failed to classify batch {batch_num}. Error: {e}")
                # Fallback for these keys
                for key in batch_keys:
                    classifications[key] = {
                        "category": "Review Narration",
                        "nature": "Unknown",
                        "description": f"AI classification error: {str(e)}",
                        "confidence": 0
                    }

            # Update matching transactions in-place
            for txn in classified_transactions:
                if not txn.get("requires_ai", True):
                    continue

                norm_narration = txn.get("normalized_narration", "")
                key = self._generate_key(norm_narration, txn.get("debit", 0.0))
                if key in classifications:
                    classification = classifications[key]
                    txn["category"] = classification.get("category", "Review Narration")
                    txn["nature"] = classification.get("nature", "Unknown")
                    txn["description"] = classification.get("description", "")
                    txn["confidence"] = classification.get("confidence", 0)

            # Trigger callback after each batch completes
            if on_batch_complete:
                on_batch_complete(classified_transactions)

        logger.info("Finished applying classifications.")
        return classified_transactions
