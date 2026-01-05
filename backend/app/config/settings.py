import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# ASR and TTS API URLs
ASR_API_URL = os.getenv("ASR_API_URL", "http://27.111.72.52:5073/transcribe")
TTS_API_URL = os.getenv("TTS_API_URL", "http://27.111.72.52:5057/synthesize")
