from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    gemini_api_key: str
    asr_api_url: str
    local_tts_url: str
    database_url: str

    class Config:
        # Look for .env file in current directory and parent directory
        env_file = [
            Path(__file__).parent.parent / ".env",
            Path(__file__).parent / ".env",
            ".env",
        ]
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env


settings = Settings()
