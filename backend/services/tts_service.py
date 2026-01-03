import httpx
from config import settings
from typing import Optional, Tuple
import struct


def pcm_to_wav(
    pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2
) -> bytes:
    """Convert raw PCM audio data to WAV format"""
    # WAV file header structure
    # RIFF header
    riff_header = b"RIFF"
    # File size (will be updated later)
    file_size = 0
    # WAVE header
    wave_header = b"WAVE"
    # fmt chunk
    fmt_chunk_id = b"fmt "
    fmt_chunk_size = struct.pack("<I", 16)  # 16 bytes for PCM
    audio_format = struct.pack("<H", 1)  # 1 = PCM
    num_channels = struct.pack("<H", channels)
    sample_rate_bytes = struct.pack("<I", sample_rate)
    byte_rate = struct.pack("<I", sample_rate * channels * sample_width)
    block_align = struct.pack("<H", channels * sample_width)
    bits_per_sample = struct.pack("<H", sample_width * 8)
    # data chunk
    data_chunk_id = b"data"
    data_size = struct.pack("<I", len(pcm_data))

    # Calculate total file size
    file_size = 4 + 8 + 16 + 8 + len(pcm_data)  # RIFF + WAVE + fmt + data header + data
    file_size_bytes = struct.pack("<I", file_size)

    # Combine all parts
    wav_data = (
        riff_header
        + file_size_bytes
        + wave_header
        + fmt_chunk_id
        + fmt_chunk_size
        + audio_format
        + num_channels
        + sample_rate_bytes
        + byte_rate
        + block_align
        + bits_per_sample
        + data_chunk_id
        + data_size
        + pcm_data
    )

    return wav_data


def detect_sample_rate(audio_bytes: bytes, response_headers: dict = None) -> int:
    """Detect sample rate from audio bytes or headers

    Args:
        audio_bytes: Audio data
        response_headers: Optional HTTP response headers

    Returns:
        Detected sample rate (default: 22050 for TTS, 16000 for VAD)
    """
    # Method 1: Check response headers
    if response_headers:
        if "X-Sample-Rate" in response_headers:
            return int(response_headers["X-Sample-Rate"])
        if "Content-Type" in response_headers:
            ct = response_headers["Content-Type"]
            if "rate=" in ct:
                return int(ct.split("rate=")[1].split(";")[0])

    # Method 2: Read from WAV header
    if len(audio_bytes) >= 44:
        if audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
            sample_rate = struct.unpack("<I", audio_bytes[24:28])[0]
            print(f"✅ Detected sample rate from WAV header: {sample_rate} Hz")
            return sample_rate

    # Method 3: Try pydub for other formats (MP3, OGG, WebM, etc.)
    try:
        from pydub import AudioSegment
        import io

        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        sample_rate = audio.frame_rate
        print(f"✅ Detected sample rate using pydub: {sample_rate} Hz")
        return sample_rate
    except Exception as e:
        print(f"⚠️ Could not detect sample rate with pydub: {e}")

    # Default fallback - TTS typically uses 24000 Hz
    default_rate = 24000
    print(f"⚠️ Using default TTS sample rate: {default_rate} Hz")
    return default_rate


async def synthesize_speech(
    text: str, language: str = "hi", speed: float = 1.0
) -> Optional[Tuple[bytes, int]]:
    """Convert text to speech using TTS API

    Args:
        text: Text to synthesize
        language: Language code (default: "hi" for Hindi)
        speed: Speech speed/rate (default: 1.0, normal speed. Higher = faster, e.g., 1.2 = 20% faster)

    Returns:
        Tuple of (audio_bytes, sample_rate) or None if error
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Add speed parameter if TTS API supports it
            payload = {
                "text": text,
                "language": language,
                "speed": speed,  # Normal speed = 1.0, faster = >1.0 (e.g., 1.2 = 20% faster)
            }
            response = await client.post(settings.local_tts_url, json=payload)
            response.raise_for_status()
            audio_bytes = response.content

            if not audio_bytes or len(audio_bytes) < 100:
                print(
                    f"TTS Error: Received empty or too short audio ({len(audio_bytes) if audio_bytes else 0} bytes)"
                )
                return None

            # Detect sample rate from audio or headers
            detected_sample_rate = detect_sample_rate(
                audio_bytes, dict(response.headers)
            )
            print(
                f"📊 TTS Audio - Size: {len(audio_bytes)} bytes, Sample Rate: {detected_sample_rate} Hz"
            )

            # Check if audio is already in WAV format (starts with RIFF)
            if len(audio_bytes) >= 4 and audio_bytes[:4] == b"RIFF":
                print(
                    f"✅ TTS: Audio is already in WAV format ({len(audio_bytes)} bytes, {detected_sample_rate} Hz)"
                )
                return (audio_bytes, detected_sample_rate)

            # Check if it's MP3, OGG, or WebM (known formats)
            if len(audio_bytes) >= 3:
                # MP3 starts with FF FB, FF F3, or FF FA
                if audio_bytes[0] == 0xFF and audio_bytes[1] in [0xFB, 0xF3, 0xFA]:
                    print(
                        f"✅ TTS: Audio is in MP3 format ({len(audio_bytes)} bytes, {detected_sample_rate} Hz)"
                    )
                    return (audio_bytes, detected_sample_rate)
                # OGG starts with OggS
                if len(audio_bytes) >= 4 and audio_bytes[:4] == b"OggS":
                    print(
                        f"✅ TTS: Audio is in OGG format ({len(audio_bytes)} bytes, {detected_sample_rate} Hz)"
                    )
                    return (audio_bytes, detected_sample_rate)
                # WebM starts with 1A 45 DF A3
                if len(audio_bytes) >= 4 and audio_bytes[:4] == bytes(
                    [0x1A, 0x45, 0xDF, 0xA3]
                ):
                    print(
                        f"✅ TTS: Audio is in WebM format ({len(audio_bytes)} bytes, {detected_sample_rate} Hz)"
                    )
                    return (audio_bytes, detected_sample_rate)

            # Check if it's raw PCM (starts with zeros or no known header)
            # Find first non-zero byte
            first_non_zero = -1
            for i in range(min(1000, len(audio_bytes))):
                if audio_bytes[i] != 0:
                    first_non_zero = i
                    break

            if first_non_zero > 0 or (first_non_zero == -1 and len(audio_bytes) > 1000):
                # Might be PCM data - try to convert to WAV
                print(
                    f"TTS: Audio appears to be PCM (first non-zero at {first_non_zero}), converting to WAV..."
                )
                # Remove leading zeros
                pcm_data = (
                    audio_bytes[first_non_zero:] if first_non_zero > 0 else audio_bytes
                )
                # Remove trailing zeros
                pcm_data = pcm_data.rstrip(b"\x00")

                if len(pcm_data) > 0:
                    try:
                        # Use detected sample rate instead of hardcoded 16000
                        wav_data = pcm_to_wav(
                            pcm_data,
                            sample_rate=detected_sample_rate,
                            channels=1,
                            sample_width=2,
                        )
                        print(
                            f"✅ TTS: Converted {len(pcm_data)} bytes PCM to {len(wav_data)} bytes WAV "
                            f"(sample rate: {detected_sample_rate} Hz)"
                        )
                        return (wav_data, detected_sample_rate)
                    except Exception as conv_error:
                        print(f"❌ TTS: Error converting PCM to WAV: {conv_error}")
                        # Return original as fallback
                        return (audio_bytes, detected_sample_rate)
                else:
                    print(f"⚠️ TTS: PCM data is all zeros after trimming")
                    return None

            # Unknown format, return as-is (browser will try to decode)
            print(
                f"⚠️ TTS: Unknown audio format, returning as-is ({len(audio_bytes)} bytes, {detected_sample_rate} Hz)"
            )
            return (audio_bytes, detected_sample_rate)

    except Exception as e:
        print(f"❌ TTS Error: {str(e)}")
        import traceback

        traceback.print_exc()
        return None
