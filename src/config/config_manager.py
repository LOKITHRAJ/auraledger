import os
import json
import base64
import logging
from pathlib import Path

logger = logging.getLogger("AuraLedger")


# --- Windows DPAPI Encryption Bindings via ctypes ---
try:
    import ctypes
    from ctypes import wintypes

    # ctypes.windll only exists on Windows -- everything below only references
    # it inside function bodies, so without this check the import itself
    # "succeeds" on Linux/Mac too, and the AttributeError only surfaces later
    # at call time, where it gets silently swallowed by get_api_key()/
    # set_api_key()'s own error handling instead of falling back to Base64.
    if not hasattr(ctypes, "windll"):
        raise RuntimeError("ctypes.windll is only available on Windows")

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    def _encrypt_dpapi(secret_str: str) -> str:
        if not secret_str:
            return ""
        data_bytes = secret_str.encode("utf-8")
        in_blob = DATA_BLOB(len(data_bytes), ctypes.cast(ctypes.create_string_buffer(data_bytes), ctypes.POINTER(ctypes.c_byte)))
        out_blob = DATA_BLOB()
        
        crypt32 = ctypes.windll.crypt32
        if crypt32.CryptProtectData(ctypes.byref(in_blob), "AuraLedgerIQ_Secret", None, None, None, 0, ctypes.byref(out_blob)):
            result = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
            return base64.b64encode(result).decode("utf-8")
        raise Exception("DPAPI Encryption Failed")

    def _decrypt_dpapi(encrypted_base64: str) -> str:
        if not encrypted_base64:
            return ""
        encrypted_bytes = base64.b64decode(encrypted_base64.encode("utf-8"))
        in_blob = DATA_BLOB(len(encrypted_bytes), ctypes.cast(ctypes.create_string_buffer(encrypted_bytes), ctypes.POINTER(ctypes.c_byte)))
        out_blob = DATA_BLOB()
        
        crypt32 = ctypes.windll.crypt32
        if crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
            result = ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8")
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
            return result
        raise Exception("DPAPI Decryption Failed")

except Exception as e:
    logger.warning(f"DPAPI not available (non-Windows system). Falling back to Base64: {e}")
    # Fallback to simple Base64 for development environments
    def _encrypt_dpapi(secret_str: str) -> str:
        return base64.b64encode(secret_str.encode("utf-8")).decode("utf-8") if secret_str else ""

    def _decrypt_dpapi(encrypted_base64: str) -> str:
        return base64.b64decode(encrypted_base64.encode("utf-8")).decode("utf-8") if encrypted_base64 else ""


class ConfigManager:
    """
    Manages local application configurations stored in AppData.
    Encrypts sensitive data (API Keys) using Windows DPAPI.
    """

    def __init__(self) -> None:
        self.appdata_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".auraledger"))) / "AuraLedgerIQ"
        self.settings_path = self.appdata_dir / "settings.json"
        
        # Default Settings configuration
        self.defaults = {
            "theme": "Enterprise Light Mode",
            "ai_provider": "Gemini",
            "api_key_encrypted": "",
            "batch_size": 20,
            "auto_save": True,
            "output_folder": str(Path("output").absolute()),
            # Empty means "no custom password set" — auth falls back to the default admin123 password
            "admin_password_hash": ""
        }

    def load_config(self) -> dict:
        """
        Loads user settings from file. Defaults values if settings file is missing.
        """
        if not self.settings_path.exists():
            return self.defaults.copy()
            
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                
            # Merge missing defaults if settings file is outdated
            for k, v in self.defaults.items():
                if k not in config:
                    config[k] = v
            return config
        except Exception as e:
            logger.error(f"Failed to read settings: {e}")
            return self.defaults.copy()

    def save_config(self, config: dict) -> bool:
        """
        Saves user settings to file, ensuring AppData directory exists.
        """
        try:
            self.appdata_dir.mkdir(parents=True, exist_ok=True)
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def get_api_key(self) -> str:
        """
        Decrypts and returns the saved API Key.
        """
        config = self.load_config()
        encrypted = config.get("api_key_encrypted", "")
        try:
            return _decrypt_dpapi(encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt API Key: {e}")
            return ""

    def set_api_key(self, key_str: str) -> bool:
        """
        Encrypts and stores the API Key in the settings file.
        """
        config = self.load_config()
        try:
            config["api_key_encrypted"] = _encrypt_dpapi(key_str)
            return self.save_config(config)
        except Exception as e:
            logger.error(f"Failed to encrypt API Key: {e}")
            return False
