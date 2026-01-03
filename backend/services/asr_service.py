import httpx
from config import settings
from typing import Optional


async def transcribe_audio(audio_data: bytes, content_type: str = "audio/wav") -> Optional[str]:
    """Convert audio to text using ASR API
    
    Args:
        audio_data: Audio bytes (supports webm, wav, etc.)
        content_type: MIME type of the audio (default: audio/wav)
    
    Returns:
        Transcribed text or None if error
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        print(f"\n{'='*80}")
        print(f"🔊 CALLING ASR SERVICE...")
        print(f"   URL: {settings.asr_api_url}")
        print(f"   Audio size: {len(audio_data)} bytes")
        print(f"   Content type: {content_type}")
        print(f"{'='*80}\n")
        logger.info(f"🔊 Calling ASR service: {settings.asr_api_url} ({len(audio_data)} bytes)")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Determine file extension from content type
            ext = "wav" if "wav" in content_type else "webm"
            files = {"file": (f"audio.{ext}", audio_data, content_type)}
            response = await client.post(settings.asr_api_url, files=files)
            response.raise_for_status()
            result = response.json()
            
            # Extract transcription (handle different response formats)
            transcription = result.get("transcription") or result.get("text", "").strip()
            
            if transcription:
                print(f"\n{'='*80}")
                print(f"✅ ASR TRANSCRIPTION RECEIVED:")
                print(f"   Text: '{transcription}'")
                if "detected_language" in result:
                    print(f"   Language: {result.get('detected_language')} (confidence: {result.get('language_confidence', 0):.2f})")
                if "is_code_mixed" in result:
                    print(f"   Code-mixed: {result.get('is_code_mixed')}")
                print(f"{'='*80}\n")
                logger.info(f"✅ ASR Transcription: '{transcription}'")
            else:
                print(f"\n{'='*80}")
                print(f"⚠️ ASR RETURNED EMPTY TRANSCRIPTION")
                print(f"   Response: {result}")
                print(f"{'='*80}\n")
                logger.warning(f"⚠️ ASR returned empty transcription. Response: {result}")
            
            return transcription
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ ASR ERROR:")
        print(f"   Error: {str(e)}")
        print(f"{'='*80}\n")
        logger.error(f"❌ ASR Error: {str(e)}", exc_info=True)
        return None

