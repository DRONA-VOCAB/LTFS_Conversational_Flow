"""ASR Service using API"""

import os
import io
import traceback
import logging
import httpx
from typing import Dict, Any, Optional
from config.settings import ASR_API_URL

logger = logging.getLogger(__name__)

# Allowed dominant languages
ALLOWED_LANGUAGES = ["hi", "en"]


# ---------------------------------------------------------
# Helper: Detect Hinglish (code-mix)
# ---------------------------------------------------------
def detect_code_mix(text: str) -> bool:
    has_hi = any("\u0900" <= c <= "\u097f" for c in text)
    has_en = any("a" <= c.lower() <= "z" for c in text)
    return has_hi and has_en


# ---------------------------------------------------------
# ASR Processing
# ---------------------------------------------------------
async def transcribe_audio(
    audio_bytes: bytes, save_dir: str = "output_audios"
) -> Dict[str, Any]:
    """
    Transcribe audio bytes using ASR API

    Args:
        audio_bytes: Raw audio bytes (WAV format expected)
        save_dir: Directory to save audio files for debugging (not used for API)

    Returns:
        Dictionary with transcription results
    """
    try:
        logger.info(
            f"🎤 ASR: Starting transcription, audio size: {len(audio_bytes)} bytes"
        )
        logger.info(f"🎤 ASR: API URL: {ASR_API_URL}/transcribe")

        # Prepare file for multipart/form-data
        files = {"file": ("audio.wav", io.BytesIO(audio_bytes), "audio/wav")}

        # Make API call to ASR service
        logger.info(f"📤 ASR: Sending POST request to {ASR_API_URL}/transcribe")
        logger.info(
            f"📤 ASR: Payload: multipart/form-data with audio.wav ({len(audio_bytes)} bytes)"
        )
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{ASR_API_URL}/transcribe", files=files)
            logger.info(f"📥 ASR: Response status: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            logger.info(f"📥 ASR: Response received: {result}")

        # Extract transcription and metadata
        transcription = result.get("transcription", "").strip()
        detected_lang = result.get("detected_language", "en")
        detected_conf = result.get("language_confidence", 0.0)
        forced_lang = result.get("forced_language", detected_lang)
        is_code_mixed = result.get("is_code_mixed", False)
        segments = result.get("segments", [])

        logger.info(f"✅ ASR: Transcription: '{transcription}'")
        logger.info(
            f"✅ ASR: Detected language: {detected_lang}, Confidence: {detected_conf:.2f}"
        )
        logger.info(
            f"✅ ASR: Forced language: {forced_lang}, Code-mixed: {is_code_mixed}"
        )

        # Return in same format as before
        return {
            "detected_language": detected_lang,
            "language_confidence": detected_conf,
            "forced_language": forced_lang,
            "is_code_mixed": is_code_mixed,
            "transcription": transcription,
            "segments": segments,
        }
    except httpx.HTTPError as e:
        logger.error(f"❌ ASR: HTTP Error: {e}")
        logger.error(f"❌ ASR: Request URL: {ASR_API_URL}/transcribe")
        if hasattr(e, "response") and e.response:
            logger.error(f"❌ ASR: Response status: {e.response.status_code}")
            logger.error(f"❌ ASR: Response text: {e.response.text[:500]}")
        return {"error": f"ASR API error: {str(e)}", "transcription": ""}
    except Exception as e:
        logger.error(f"❌ ASR: Error: {e}")
        traceback.print_exc()
        return {"error": str(e), "transcription": ""}
