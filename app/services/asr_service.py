"""ASR (Speech-to-Text) service integration."""
import httpx
from typing import Optional
import time
from app.config import settings


class ASRService:
    """Service for converting speech to text."""
    
    def __init__(self):
        self.asr_url = settings.asr_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def transcribe(self, audio_data: bytes, audio_format: str = "wav") -> Optional[str]:
        """
        Transcribe audio to text.
        
        Args:
            audio_data: Audio bytes
            audio_format: Audio format (wav, mp3, etc.)
        
        Returns:
            Transcribed text or None if error
        """
        start_time = time.perf_counter()
        try:
            files = {
                "file": ("audio." + audio_format, audio_data, f"audio/{audio_format}")
            }
            
            response = await self.client.post(
                self.asr_url,
                files=files
            )
            
            latency = time.perf_counter() - start_time
            
            if response.status_code == 200:
                result = response.json()
                # Adjust based on actual API response format
                transcribed_text = None
                if isinstance(result, dict):
                    transcribed_text = result.get("text") or result.get("transcription")
                elif isinstance(result, str):
                    transcribed_text = result
                else:
                    transcribed_text = str(result)
                
                if transcribed_text:
                    print(f"[ASR] Transcription latency: {latency:.3f}s, audio size: {len(audio_data)} bytes, text: '{transcribed_text[:50]}...'")
                else:
                    print(f"[ASR] Transcription latency: {latency:.3f}s, but no text extracted")
                return transcribed_text
            else:
                print(f"[ASR] Error: {response.status_code} - {response.text} (latency: {latency:.3f}s)")
                return None
                
        except Exception as e:
            latency = time.perf_counter() - start_time
            print(f"[ASR] Exception: {str(e)} (latency: {latency:.3f}s)")
            return None
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

