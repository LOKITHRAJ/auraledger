import logging
import sys
from pathlib import Path


def read_prompt(file_name: str) -> str:
    """
    Reads prompt file content. Checks root prompts folder first, then falls back to src/prompts.
    """
    base_dir = Path(__file__).resolve().parent.parent
    
    # Try workspace_root/prompts
    prompt_path = base_dir / "prompts" / file_name
    if not prompt_path.exists():
        # Fall back to workspace_root/src/prompts
        prompt_path = base_dir / "src" / "prompts" / file_name

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_name}")

    with open(prompt_path, "r", encoding="utf-8") as file:
        return file.read()


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Configures and returns a logger that logs to both console and a log file.
    """
    logger = logging.getLogger("AuraLedger")
    if logger.hasHandlers():
        return logger

    logger.setLevel(level)

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "auraledger.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger