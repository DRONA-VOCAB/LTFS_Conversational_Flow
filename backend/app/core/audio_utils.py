"""
Audio Utilities
Shared utilities for audio file handling and processing
"""

import asyncio
import io
import logging
import wave
from pathlib import Path
from typing import Dict

from config.settings import PUBLIC_BASE_URL

logger = logging.getLogger(__name__)

# Audio directories
AUDIO_ROOT = Path(__file__).resolve().parents[2] / "audio_files"
ASR_AUDIO_DIR = AUDIO_ROOT / "asr_audios"
TTS_AUDIO_DIR = AUDIO_ROOT / "tts_audios"
ASR_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
TTS_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Audio parameters
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit PCM


def pcm16_to_wav(pcm_bytes, sample_rate=SAMPLE_RATE, channels=CHANNELS):
    """Convert raw 16-bit PCM audio bytes to WAV format"""
    with io.BytesIO() as wav_buffer:
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return wav_buffer.getvalue()


def prepare_audio_bytes(raw_bytes: bytes) -> bytes:
    """
    Ensure bytes are WAV formatted

    Args:
        raw_bytes: Raw audio bytes (may be PCM or WAV)

    Returns:
        WAV formatted audio bytes
    """
    if raw_bytes[:4] == b"RIFF":
        return raw_bytes
    return pcm16_to_wav(raw_bytes)


def build_audio_url(folder: str, filename: str) -> str:
    """
    Build public URL for audio file

    Args:
        folder: Folder name (asr_audios or tts_audios)
        filename: Audio filename

    Returns:
        Full public URL
    """
    base = PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/{folder}/{filename}"


def save_audio_file(path: Path, data: bytes) -> None:
    """
    Save audio file to disk

    Args:
        path: File path
        data: Audio bytes
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def save_audio_non_blocking(path: Path, data: bytes) -> None:
    """
    Save audio file asynchronously (non-blocking)

    Args:
        path: File path
        data: Audio bytes
    """
    asyncio.create_task(asyncio.to_thread(save_audio_file, path, data))


def sanitize_session_id(session_id: str) -> str:
    """
    Sanitize session ID for use in filenames

    Args:
        session_id: Raw session ID

    Returns:
        Sanitized session ID
    """
    return (session_id or "session").replace(" ", "_")


def get_next_turn_id(state: Dict, session_id: str) -> str:
    """
    Generate next turn ID for audio file naming

    Args:
        state: Connection state dict
        session_id: Session ID

    Returns:
        Turn ID string (e.g., "session_turn001")
    """
    counter = state.get("turn_counter", 0) + 1
    state["turn_counter"] = counter
    return f"{sanitize_session_id(session_id)}_turn{counter:03d}"
