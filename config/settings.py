# config/config.py
from dataclasses import dataclass
import os


@dataclass
class OpenaiConfig:
    api_key: str = os.getenv("OPENAI_API_KEY") or ""
    base_url: str = os.getenv("OPENAI_BASE_URL") or ""
    model: str = os.getenv("OPENAI_MODEL") or ""


@dataclass
class AppConfig:
    openai: OpenaiConfig = OpenaiConfig()
    env: str = os.getenv("ENV") or "develop"
    log_level: str = os.getenv("LOG_LEVEL") or "INFO"


app_config = AppConfig()
