"""Configuration settings for the application."""
import os
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional

class Settings(BaseSettings):
    """Application settings."""
    
    # API Keys
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    
    # Service URLs
    asr_url: str = os.getenv("ASR_URL", "http://27.111.72.52:5073/transcribe")
    tts_url: str = os.getenv("TTS_URL", "http://27.111.72.52:5057/synthesize")
    
    # TTS Voice Settings
    tts_voice_parameter: str = os.getenv("TTS_VOICE_PARAMETER", "speaker")  
    tts_female_voice_value: str = os.getenv("TTS_FEMALE_VOICE_VALUE", "female")  
    
    # Database
    database_url: Optional[str] = os.getenv("DATABASE_URL")
    
    # Application
    app_name: str = "L&T Finance Feedback Survey"
    app_version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Compliance thresholds
    payment_amount_tolerance: float = 500.0  
    payment_date_tolerance_hours: int = 48  
    
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"  # Ignore extra environment variables that aren't defined in the model
    )


settings = Settings()

