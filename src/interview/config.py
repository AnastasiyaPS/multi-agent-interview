from __future__ import annotations
from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    log_path: str = "interview_log.json"

    use_mistral: bool = True
    mistral_api_key: str = os.getenv("MISTRAL_API_KEY", "")
    mistral_model: str = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

settings = Settings()
