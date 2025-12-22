"""TTS (Text-to-Speech) service integration."""
import httpx
from typing import Optional, Tuple
import struct
import time
from app.config import settings


class TTSService:
    """Service for converting text to speech."""
    
    def __init__(self):
        self.tts_url = settings.tts_url
        # Increased timeout for large audio files and added retry support
        self.client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
    
    async def synthesize_with_retry(self, text: str, language: str = "en", voice: Optional[str] = None, max_retries: int = 2) -> Tuple[Optional[bytes], float]:
        """
        Synthesize with retry logic for handling connection errors.
        
        Returns:
            Tuple of (audio_bytes, latency_in_seconds)
        """
        start_time = time.perf_counter()
        total_latency = 0.0
        
        for attempt in range(max_retries + 1):
            attempt_start = time.perf_counter()
            audio = await self.synthesize(text, language, voice)
            attempt_latency = time.perf_counter() - attempt_start
            total_latency += attempt_latency
            
            if audio is not None and len(audio) > 0:
                final_latency = time.perf_counter() - start_time
                print(f"[TTS] Latency: {final_latency:.3f}s (attempt {attempt + 1}, {attempt_latency:.3f}s)")
                return audio, final_latency
            if attempt < max_retries:
                print(f"[TTS] Retry attempt {attempt + 1}/{max_retries} for: {text[:50]}... (latency: {attempt_latency:.3f}s)")
                import asyncio
                await asyncio.sleep(0.5)  # Brief delay before retry
        
        final_latency = time.perf_counter() - start_time
        print(f"[TTS] Failed to synthesize after {max_retries + 1} attempts (total latency: {final_latency:.3f}s)")
        return None, final_latency
    
    async def synthesize(self, text: str, language: str = "en", voice: Optional[str] = None) -> Optional[bytes]:
        """
        Synthesize text to speech.
        
        Args:
            text: Text to convert to speech
            language: Language code (en, hi, etc.)
            voice: Voice type (female, male) - if None, uses TTS service default
        
        Returns:
            Audio bytes or None if error
        """
        start_time = time.perf_counter()
        try:
            # Build payload with text and language only (use TTS service default voice)
            payload = {
                "text": text,
                "language": language,
            }

            # Only add voice parameters if explicitly specified
            if voice:
                if voice == "female":
                    payload["speaker"] = "female"
                    payload["voice"] = "female"
                    payload["gender"] = "female"
                elif voice == "male":
                    payload["speaker"] = "male"
                    payload["voice"] = "male"
                    payload["gender"] = "male"
            
            payload["rate"] = 1.0                # Normal speed
            payload["speed"] = 1.0       # Some APIs use "speed"
            payload["speaking_rate"] = 1.0 # Others use "speaking_rate"

            print(f"[TTS] Voice setting: {voice if voice else 'default (not specified)'}")
            print(f"[TTS] Request payload being sent:")
            for key, value in payload.items():
                print(f"  {key}: {value}")
            
            response = await self.client.post(
                self.tts_url,
                json=payload
            )
            
            print(f"[TTS] Response status: {response.status_code}")
            if response.status_code != 200:
                print(f"[TTS] Response error: {response.text[:200]}")
            
            if response.status_code == 200:
                # Check if response is JSON with audio data or direct audio
                content_type = response.headers.get("content-type", "")
                
                if "application/json" in content_type:
                    result = response.json()
                    print(f"[TTS] Received JSON response. Keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
                    
                    # Adjust based on actual API response format
                    audio_base64 = None
                    if "audio" in result:
                        audio_base64 = result["audio"]
                    elif "audio_data" in result:
                        audio_base64 = result["audio_data"]
                    elif "data" in result:
                        audio_base64 = result["data"]
                    
                    if audio_base64:
                        import base64
                        try:
                            audio_bytes = base64.b64decode(audio_base64)
                            print(f"[TTS] Decoded JSON audio, {len(audio_bytes)} bytes")
                            
                            # Validate decoded audio
                            if len(audio_bytes) == 0:
                                print("[TTS] ERROR: Decoded audio is empty!")
                                return None
                            
                            # Fix audio format (strip zeros, add header)
                            audio_bytes = self._fix_audio_format(audio_bytes)
                            return audio_bytes
                        except Exception as e:
                            print(f"[TTS] ERROR: Failed to decode base64 audio: {e}")
                            return None
                    else:
                        print(f"[TTS] ERROR: JSON response but no audio field found. Response: {str(result)[:200]}")
                        return None
                else:
                    # Direct audio response
                    audio_bytes = response.content
                    print(f"[TTS] Received direct audio ({content_type}), {len(audio_bytes)} bytes")
                    
                    # Validate audio data
                    if len(audio_bytes) == 0:
                        print("[TTS] ERROR: Received empty audio data!")
                        return None
                    
                    # Check if entire file is zeros (corrupted)
                    # We allow leading zeros which will be stripped, but reject if ALL bytes are zero
                    non_zero_count = sum(1 for b in audio_bytes if b != 0)
                    if non_zero_count == 0:
                        print("[TTS] ERROR: Entire audio file is zeros - corrupted!")
                        return None
                    
                    # Find first non-zero byte to log leading zeros
                    first_non_zero = None
                    for i, b in enumerate(audio_bytes[:2000]):  # Check first 2000 bytes
                        if b != 0:
                            first_non_zero = i
                            break
                    
                    if first_non_zero and first_non_zero > 100:
                        print(f"[TTS] INFO: Found {first_non_zero} leading zero bytes - will be stripped")
                    elif first_non_zero is None:
                        # Audio data starts after first 2000 bytes - unusual but valid
                        print(f"[TTS] INFO: Audio data starts after first 2000 bytes")
                    
                    # Log first few bytes to help identify format
                    if len(audio_bytes) >= 8:
                        header_bytes = audio_bytes[:8]
                        header_hex = ' '.join([f'{b:02x}' for b in header_bytes])
                        header_ascii = ''.join([chr(b) if 32 <= b < 127 else '.' for b in header_bytes])
                        print(f"[TTS] Audio header (hex): {header_hex}")
                        print(f"[TTS] Audio header (ascii): {header_ascii}")
                        
                        # Detect format
                        if audio_bytes[:4] == b'RIFF':
                            print("[TTS] Detected format: WAV")
                        elif audio_bytes[:3] == b'ID3' or (audio_bytes[0] == 0xFF and audio_bytes[1] in [0xFB, 0xF3, 0xF2]):
                            print("[TTS] Detected format: MP3")
                        elif audio_bytes[:4] == b'OggS':
                            print("[TTS] Detected format: OGG")
                        elif audio_bytes[:4] == b'\x1a\x45\xdf\xa3':
                            print("[TTS] Detected format: WebM")
                        elif audio_bytes[:4] == b'fLaC':
                            print("[TTS] Detected format: FLAC")
                        else:
                            print("[TTS] Unknown audio format - may need format detection")
                            # Check if it's mostly zeros (corrupted)
                            non_zero = sum(1 for b in audio_bytes[:100] if b != 0)
                            if non_zero < 10:
                                print("[TTS] WARNING: Audio appears corrupted (mostly zeros)")
                    
                    # Fix: Strip leading zeros and add WAV header if needed
                    audio_bytes = self._fix_audio_format(audio_bytes)
                    latency = time.perf_counter() - start_time
                    print(f"[TTS] Synthesis latency: {latency:.3f}s, audio size: {len(audio_bytes)} bytes")
                    return audio_bytes
            else:
                latency = time.perf_counter() - start_time
                print(f"[TTS] Error: {response.status_code} - {response.text} (latency: {latency:.3f}s)")
                return None
                
        except httpx.ReadTimeout:
            latency = time.perf_counter() - start_time
            print(f"[TTS] Error: Request timeout - TTS service took too long to respond (latency: {latency:.3f}s)")
            return None
        except httpx.ConnectError as e:
            latency = time.perf_counter() - start_time
            print(f"[TTS] Error: Connection error - {str(e)} (latency: {latency:.3f}s)")
            return None
        except httpx.ReadError as e:
            latency = time.perf_counter() - start_time
            print(f"[TTS] Error: Read error (incomplete response) - {str(e)} (latency: {latency:.3f}s)")
            # This can happen if TTS service closes connection early
            # Try to read partial content if available
            try:
                if hasattr(response, 'content') and response.content:
                    audio_bytes = response.content
                    if len(audio_bytes) > 1000:  # Only use if we have substantial data
                        print(f"[TTS] Using partial audio data: {len(audio_bytes)} bytes")
                        audio_bytes = self._fix_audio_format(audio_bytes)
                        return audio_bytes
            except:
                pass
            return None
        except Exception as e:
            latency = time.perf_counter() - start_time
            print(f"[TTS] Exception: {str(e)} (latency: {latency:.3f}s)")
            import traceback
            print(f"[TTS] Traceback: {traceback.format_exc()}")
            return None
    
    def _fix_audio_format(self, audio_bytes: bytes) -> bytes:
        """
        Fix audio format issues:
        1. Strip leading zeros
        2. Add WAV header if missing
        """
        if not audio_bytes or len(audio_bytes) == 0:
            return audio_bytes
        
        # First, strip any leading zeros that some TTS servers prepend.
        first_non_zero = 0
        for i, b in enumerate(audio_bytes):
            if b != 0:
                first_non_zero = i
                break

        if first_non_zero > 0:
            print(f"[TTS] Stripping {first_non_zero} leading zero bytes")
            audio_bytes = audio_bytes[first_non_zero:]

        # After stripping zeros, if it now starts with a WAV header,
        # keep the original header/sample rate exactly as provided.
        if len(audio_bytes) >= 4 and audio_bytes[:4] == b'RIFF':
            print("[TTS] Audio already has WAV header after zero-strip")
            return audio_bytes

        # Otherwise, treat it as raw PCM (no header) and wrap it in
        # a standard WAV header. Use a conservative, human-sounding
        # 16 kHz mono default which most TTS engines use for telephony.
        sample_rate = 24000  # 16 kHz for natural speech
        channels = 1         # mono
        bits_per_sample = 16 # 16‑bit PCM
        
        # Add WAV header
        wav_header = self._create_wav_header(len(audio_bytes), sample_rate, channels, bits_per_sample)
        return wav_header + audio_bytes
    
    def _create_wav_header(self, data_size: int, sample_rate: int, channels: int, bits_per_sample: int) -> bytes:
        """Create a standard WAV file header."""
        # WAV file structure:
        # - RIFF header (12 bytes)
        # - fmt chunk (24 bytes)
        # - data chunk header (8 bytes)
        # - audio data
        
        # Calculate sizes
        fmt_chunk_size = 16  # Standard PCM fmt chunk size
        data_chunk_size = data_size
        file_size = 36 + data_chunk_size  # 36 = 12 (RIFF) + 24 (fmt) + 8 (data header)
        
        # RIFF header
        header = b'RIFF'
        header += struct.pack('<I', file_size)  # File size - 8
        header += b'WAVE'
        
        # fmt chunk
        header += b'fmt '
        header += struct.pack('<I', fmt_chunk_size)  # fmt chunk size
        header += struct.pack('<H', 1)  # Audio format (1 = PCM)
        header += struct.pack('<H', channels)  # Number of channels
        header += struct.pack('<I', sample_rate)  # Sample rate
        header += struct.pack('<I', sample_rate * channels * (bits_per_sample // 8))  # Byte rate
        header += struct.pack('<H', channels * (bits_per_sample // 8))  # Block align
        header += struct.pack('<H', bits_per_sample)  # Bits per sample
        
        # data chunk
        header += b'data'
        header += struct.pack('<I', data_chunk_size)  # Data size
        
        return header
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

