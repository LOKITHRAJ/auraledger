import json
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("AuraLedger")


# --- Schema Definition for Structured Output ---

class ClassifiedTransaction(BaseModel):
    date: str = Field(description="The date of the transaction")
    narration: str = Field(description="The narration or description of the transaction")
    debit: float = Field(description="The debit/withdrawal amount")
    credit: float = Field(description="The credit/deposit amount")
    balance: float = Field(description="The closing balance")
    category: str = Field(description="The business category of the transaction")
    description: str = Field(description="A concise description useful for an auditor")
    nature: str = Field(description="The nature of the transaction, which MUST be selected from the predefined list of allowed values such as Salary Payment, Vendor Payment, Bank Charges, UPI Payment, etc. Use 'Unknown' if none match.")
    confidence: int = Field(description="Your confidence score in this classification as an integer percentage from 0 to 100")


class ClassificationResponse(BaseModel):
    transactions: List[ClassifiedTransaction]


# --- Abstract Base Client ---

class BaseAIClient(ABC):
    """
    Abstract Base Class for AI Clients, allowing swapping of LLM providers.
    """

    @abstractmethod
    def classify_batch(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sends a batch of transactions to the AI model and returns classified transactions.
        """
        pass


# --- Gemini Implementation ---

class GeminiAIClient(BaseAIClient):
    """
    Client for interacting with Google Gemini Flash API using the new google-genai SDK.
    """

    def __init__(self) -> None:
        from config.settings import GEMINI_API_KEY, GEMINI_MODEL
        from utils import read_prompt
        
        api_key = GEMINI_API_KEY
        if not api_key:
            try:
                from config.config_manager import ConfigManager
                api_key = ConfigManager().get_api_key()
            except Exception:
                pass
        
        if not api_key:
            raise ValueError(
                "API Key is not configured. Please launch the AuraLedgerIQ Setup Wizard."
            )
            
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model = GEMINI_MODEL
        self.system_prompt = read_prompt("classifier_prompt.txt")
        logger.info(f"Initialized GeminiAIClient with model: {self.model}")

    def classify_batch(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        from google.genai import types

        # Prepare input JSON payload
        payload = {"transactions": transactions}
        
        logger.info(f"Sending batch of {len(transactions)} transactions to Gemini API...")

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=json.dumps(payload, indent=2),
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    response_mime_type="application/json",
                    response_schema=ClassificationResponse,
                    temperature=0.1
                )
            )

            response_text = response.text.strip()
            
            # Remove potential markdown block wraps if returned despite schema config
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "", 1)
            if response_text.endswith("```"):
                response_text = response_text.rsplit("```", 1)[0]
            response_text = response_text.strip()

            result = json.loads(response_text)
            classified_list = result.get("transactions", [])
            
            # Format to basic Python dictionary
            return [
                {
                    "date": txn.get("date", ""),
                    "narration": txn.get("narration", ""),
                    "debit": txn.get("debit", 0.0),
                    "credit": txn.get("credit", 0.0),
                    "balance": txn.get("balance", 0.0),
                    "category": txn.get("category", "Review Narration"),
                    "description": txn.get("description", ""),
                    "nature": txn.get("nature", "Unknown"),
                    "confidence": txn.get("confidence", 0)
                }
                for txn in classified_list
            ]
            
        except Exception as e:
            logger.error(f"Gemini classification failed for batch. Error: {e}")
            # Raise exception to let upper business layer handle it
            raise e


# --- OpenAI Implementation ---

class OpenAIAIClient(BaseAIClient):
    """
    Client for interacting with OpenAI API.
    """

    def __init__(self) -> None:
        from config.settings import OPENAI_API_KEY, OPENAI_MODEL
        from utils import read_prompt
        
        if not OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is not set. Please set it in your environment or .env file."
            )
            
        from openai import OpenAI
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = OPENAI_MODEL
        self.system_prompt = read_prompt("classifier_prompt.txt")
        logger.info(f"Initialized OpenAIAIClient with model: {self.model}")

    def classify_batch(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        payload = {"transactions": transactions}
        
        logger.info(f"Sending batch of {len(transactions)} transactions to OpenAI API ({self.model})...")

        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": json.dumps(payload, indent=2)}
                ],
                response_format=ClassificationResponse,
                temperature=0.1
            )
            
            parsed_response = response.choices[0].message.parsed
            if not parsed_response:
                raise ValueError("OpenAI failed to parse response into the expected schema.")
                
            classified_list = parsed_response.transactions
            
            return [
                {
                    "date": txn.date,
                    "narration": txn.narration,
                    "debit": txn.debit,
                    "credit": txn.credit,
                    "balance": txn.balance,
                    "category": txn.category if txn.category else "Review Narration",
                    "description": txn.description if txn.description else "",
                    "nature": txn.nature if txn.nature else "Unknown",
                    "confidence": txn.confidence if txn.confidence is not None else 0
                }
                for txn in classified_list
            ]
            
        except Exception as e:
            logger.error(f"OpenAI classification failed for batch. Error: {e}")
            raise e


# --- Factory Method for Instantiation ---

def get_ai_client() -> BaseAIClient:
    """
    Factory function to retrieve the configured AI Client.
    """
    from config.settings import AI_PROVIDER
    
    provider = AI_PROVIDER.lower().strip()
    
    if provider == "gemini":
        return GeminiAIClient()
    elif provider == "openai":
        return OpenAIAIClient()
    else:
        raise ValueError(
            f"Unsupported AI Provider: {AI_PROVIDER}. Predefined providers: 'gemini', 'openai'."
        )
