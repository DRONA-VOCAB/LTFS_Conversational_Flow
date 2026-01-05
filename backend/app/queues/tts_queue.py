"""TTS Queue for processing text-to-speech requests"""
import asyncio
from typing import Tuple, Optional

# Queue: (websocket, text, language, utterance_id)
tts_queue: asyncio.Queue = asyncio.Queue()

