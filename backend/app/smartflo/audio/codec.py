"""
Audio codec utilities for Smartflo integration.
Handles μ-law (G.711) encoding/decoding and base64 conversion.
"""

import audioop
import base64


def mulaw_to_pcm16(mulaw_data: bytes) -> bytes:
    """
    Convert μ-law encoded audio to PCM16 format.
    
    Args:
        mulaw_data: Raw μ-law encoded audio bytes
        
    Returns:
        PCM16 encoded audio bytes (16-bit signed integers)
    """
    # Use audioop to convert μ-law to linear PCM (16-bit)
    pcm_data = audioop.ulaw2lin(mulaw_data, 2)  # 2 bytes = 16-bit
    return pcm_data


def pcm8k_to_mulaw(pcm_8k: bytes) -> bytes:
    """
    Convert PCM16 audio to μ-law encoded format.
    
    Args:
        pcm_data: PCM16 encoded audio bytes (16-bit signed integers)
        
    Returns:
        μ-law encoded audio bytes
    """

    # Step 2: Convert PCM16 -> mu-law
    mulaw_data = audioop.lin2ulaw(pcm_8k, 2)

    return mulaw_data


def base64_decode(encoded_data: str) -> bytes:
    """
    Decode base64 string to raw bytes.
    
    Args:
        encoded_data: Base64 encoded string
        
    Returns:
        Raw bytes
    """
    return base64.b64decode(encoded_data)


def base64_encode(raw_data: bytes) -> str:
    """
    Encode raw bytes to base64 string.
    
    Args:
        raw_data: Raw bytes
        
    Returns:
        Base64 encoded string
    """
    return base64.b64encode(raw_data).decode('utf-8')


def decode_mulaw_from_base64(encoded_data: str) -> bytes:
    """
    Decode base64 encoded μ-law audio to PCM16.
    
    This is a convenience function that combines base64 decoding
    and μ-law to PCM16 conversion.
    
    Args:
        encoded_data: Base64 encoded μ-law audio
        
    Returns:
        PCM16 encoded audio bytes
    """
    mulaw_data = base64_decode(encoded_data)
    return mulaw_to_pcm16(mulaw_data)


def encode_pcm8_to_mulaw_base64(pcm_8k: bytes) -> str:
    """
    Encode PCM16 audio to base64 encoded μ-law.
    
    This is a convenience function that combines PCM16 to μ-law conversion
    and base64 encoding.
    
    Args:
        pcm_data: PCM16 encoded audio bytes
        
    Returns:
        Base64 encoded μ-law audio string
    """
    mulaw_data = pcm8k_to_mulaw(pcm_8k)
    remainder = len(mulaw_data) % 160
    if remainder != 0:
        mulaw_data += b'\xFF' * (160 - remainder)

    return base64_encode(mulaw_data)


def convert_to_8kHz(pcm16_data: bytes, original_sample_rate: int = 16000) -> bytes:
    """
    Convert PCM16 audio from original sample rate to 8000 Hz.

    Args:
        pcm16_data: PCM16 encoded audio bytes
        original_sample_rate: Original sample rate of the audio

    Returns:
        PCM16 encoded audio bytes at 8000 Hz
    """
    # Use audioop to resample the audio to 8000 Hz
    pcm_8k = audioop.ratecv(pcm16_data, 2, 1, original_sample_rate, 8000, None)[0]
    return pcm_8k


# Audio format constants
SAMPLE_RATE = 8000  # 8000 Hz as per Smartflo specification
CHANNELS = 1  # Mono
SAMPLE_WIDTH = 2  # 16-bit PCM
MULAW_SAMPLE_WIDTH = 1  # 8-bit μ-law
