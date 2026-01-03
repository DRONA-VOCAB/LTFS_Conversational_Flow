import httpx
from config import settings
from typing import Optional


async def synthesize_speech(text: str, language: str = "hi") -> Optional[bytes]:
    """Convert text to speech using TTS API"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {"text": text, "language": language}
            response = await client.post(settings.local_tts_url, json=payload)
            response.raise_for_status()
            return response.content
    except Exception as e:
        print(f"TTS Error: {str(e)}")
        return None

