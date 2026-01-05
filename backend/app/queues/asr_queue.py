"""ASR Queue for processing audio transcriptions"""
import asyncio
from typing import Tuple, Optional
from collections import deque

# Queue: (websocket, audio_bytes, utterance_id)
asr_queue: asyncio.Queue = asyncio.Queue()

