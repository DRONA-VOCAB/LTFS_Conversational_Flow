import httpx
from config import settings
from typing import Optional


async def transcribe_audio(audio_data: bytes, content_type: str = "audio/webm") -> Optional[str]:
    """Convert audio to text using ASR API
    
    Args:
        audio_data: Audio bytes (supports webm, wav, etc.)
        content_type: MIME type of the audio (default: audio/webm)
    
    Returns:
        Transcribed text or None if error
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Determine file extension from content type
            ext = "webm" if "webm" in content_type else "wav"
            files = {"file": (f"audio.{ext}", audio_data, content_type)}
            response = await client.post(settings.asr_api_url, files=files)
            response.raise_for_status()
            result = response.json()
            return result.get("text", "").strip()
    except Exception as e:
        print(f"ASR Error: {str(e)}")
        return None

