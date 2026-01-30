import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from the correct location
# Try multiple locations to find the .env file
env_paths = [
    Path(__file__).parent.parent.parent / ".env",  # backend/.env
    Path(__file__).parent.parent / ".env",  # backend/app/.env
    Path(__file__).parent / ".env",  # backend/app/config/.env
    ".env",  # current directory
]

env_loaded = False
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        env_loaded = True
        print(f"[INFO] Loaded environment from: {env_path}")
        break

if not env_loaded:
    print(
        f"[WARNING] No .env file found in any of these locations: {[str(p) for p in env_paths]}"
    )

# Server configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8001"))

GEMINI_MODEL = os.getenv("GEMINI_MODEL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# ASR, TTS, and Chatbot API URLs
ASR_API_URL = os.getenv("ASR_API_URL", "http://27.111.72.52:5073/transcribe")
TTS_API_URL = os.getenv("TTS_API_URL", "http://27.111.72.52:5057/synthesize")
CHATBOT_API_URL = os.getenv("CHATBOT_API_URL", "http://27.111.72.50:4000")
# Default to FastAPI's common local port; override in env when deployed
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://server6.vo-cab.dev:8001/")
GOOGLE_SHEET_ID = os.getenv(
    "GOOGLE_SHEET_ID",
    "1ZBAuFe0pQGzjKhg23iPh9kscqX2iO-dR8N9qAVCFFQo",
)

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL")


# Settings object for compatibility
class Settings:
    def __init__(self):
        self.host = HOST
        self.port = PORT
        self.gemini_model = GEMINI_MODEL
        self.gemini_api_key = GEMINI_API_KEY
        self.max_retries = MAX_RETRIES
        self.asr_api_url = ASR_API_URL
        self.tts_api_url = TTS_API_URL
        self.chatbot_api_url = CHATBOT_API_URL
        self.database_url = DATABASE_URL
        self.public_base_url = PUBLIC_BASE_URL
        self.google_sheet_id = GOOGLE_SHEET_ID


settings = Settings()
