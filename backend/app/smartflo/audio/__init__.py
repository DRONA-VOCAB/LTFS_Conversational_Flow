"""
Audio utilities module
"""

from .codec import (
    mulaw_to_pcm16,
    pcm8k_to_mulaw,
    base64_decode,
    base64_encode,
    decode_mulaw_from_base64,
    encode_pcm8_to_mulaw_base64,
    SAMPLE_RATE,
    CHANNELS,
    SAMPLE_WIDTH,
    MULAW_SAMPLE_WIDTH,
    convert_to_8kHz,
)
from .processor import (
    process_incoming_audio,
    generate_response_audio,
)

__all__ = [
    "mulaw_to_pcm16",
    "pcm8k_to_mulaw",
    "base64_decode",
    "base64_encode",
    "decode_mulaw_from_base64",
    "encode_pcm8_to_mulaw_base64",
    "convert_to_8kHz",
    "SAMPLE_RATE",
    "CHANNELS",
    "SAMPLE_WIDTH",
    "MULAW_SAMPLE_WIDTH",
    "process_incoming_audio",
    "generate_response_audio",
]
