# utils/event_bus.py
import asyncio
from typing import Dict
from fastapi import WebSocket

# central place to store queues and client connections to avoid circular imports
asr_queue: "asyncio.Queue" = asyncio.Queue()
llm_queue: "asyncio.Queue" = asyncio.Queue()
tts_queue: "asyncio.Queue" = asyncio.Queue()

# Map session_id -> WebSocket
clients: Dict[str, WebSocket] = {}

# Per-session audio buffers for ASR (bytes)
# ASR consumer will append chunks here until 'end' event arrives
session_audio_buffers: Dict[str, bytearray] = {}
