"""
Audio format conversion utilities
Converts PCM to WAV format
"""
import logging
import struct
from typing import Optional

logger = logging.getLogger(__name__)


def pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> bytes:
    """
    Convert raw PCM audio data to WAV format
    
    Args:
        pcm_data: Raw PCM audio bytes (16-bit, mono)
        sample_rate: Sample rate in Hz (default: 16000)
        channels: Number of audio channels (default: 1 for mono)
        sample_width: Sample width in bytes (default: 2 for 16-bit)
        
    Returns:
        WAV format audio bytes
    """
    # WAV file header structure
    # RIFF header
    riff_header = b'RIFF'
    # File size (will be updated later)
    file_size = 0
    # WAVE header
    wave_header = b'WAVE'
    # fmt chunk
    fmt_chunk_id = b'fmt '
    fmt_chunk_size = struct.pack('<I', 16)  # 16 bytes for PCM
    audio_format = struct.pack('<H', 1)  # 1 = PCM
    num_channels = struct.pack('<H', channels)
    sample_rate_bytes = struct.pack('<I', sample_rate)
    byte_rate = struct.pack('<I', sample_rate * channels * sample_width)
    block_align = struct.pack('<H', channels * sample_width)
    bits_per_sample = struct.pack('<H', sample_width * 8)
    # data chunk
    data_chunk_id = b'data'
    data_size = struct.pack('<I', len(pcm_data))
    
    # Calculate total file size
    file_size = 4 + 8 + 16 + 8 + len(pcm_data)  # RIFF + WAVE + fmt + data header + data
    file_size_bytes = struct.pack('<I', file_size)
    
    # Combine all parts
    wav_data = (
        riff_header +
        file_size_bytes +
        wave_header +
        fmt_chunk_id +
        fmt_chunk_size +
        audio_format +
        num_channels +
        sample_rate_bytes +
        byte_rate +
        block_align +
        bits_per_sample +
        data_chunk_id +
        data_size +
        pcm_data
    )
    
    return wav_data

