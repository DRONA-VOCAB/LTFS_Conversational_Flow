import collections
import logging

import numpy as np
import torch

from queues.asr_queue import asr_queue
from queues.tts_queue import tts_queue
from services.playback_state import get_playback_state
from utils.latency_tracker import start_tracking, record_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000  # Match frontend sample rate
FRAME_DURATION_MS = 32  # 32ms frames (Silero VAD requires exactly 512 samples at 16kHz)
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # 512 samples
FRAME_BYTES = FRAME_SAMPLES * 2  # 1024 bytes

model, _ = torch.hub.load(
    repo_or_dir="snakers4/silero-vad",
    model="silero_vad",
    force_reload=False,
)
model.eval()

VAD_CONFIDENCE_THRESHOLD = 0.8  # Increased to reduce false positives

VAD_WINDOW_FRAMES = 7
TRIGGER_FRAMES = 5
RELEASE_FRAMES = 2

PRE_SPEECH_MS = 500
PRE_SPEECH_FRAMES = PRE_SPEECH_MS // FRAME_DURATION_MS

TRAILING_SILENCE_MS = 800  # Increased from 500ms to 800ms for longer silence detection
TRAILING_SILENCE_FRAMES = TRAILING_SILENCE_MS // FRAME_DURATION_MS

MIN_UTTERANCE_DURATION_S = 0.8  # Minimum speech duration
MIN_UTTERANCE_BYTES = (
    int(SAMPLE_RATE * MIN_UTTERANCE_DURATION_S) * 2
)  # 25600 bytes at 16kHz


class VadState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.audio_buffer = bytearray()
        self.speech_buffer = bytearray()
        self.pre_speech = collections.deque(maxlen=PRE_SPEECH_FRAMES)
        self.vad_window = collections.deque(maxlen=VAD_WINDOW_FRAMES)
        self.trailing_silence = collections.deque(maxlen=TRAILING_SILENCE_FRAMES)
        self.in_speech = False
        self.current_utterance_id = None
        self.speech_prob = 0.0


connections = {}


def cleanup_connection(ws):
    connections.pop(ws, None)


async def process_frame(websocket, pcm_bytes: bytes, stream_sid: str):
    state = connections.setdefault(websocket, VadState())
    state.audio_buffer.extend(pcm_bytes)

    while len(state.audio_buffer) >= FRAME_BYTES:
        frame = bytes(state.audio_buffer[:FRAME_BYTES])
        del state.audio_buffer[:FRAME_BYTES]
        await process_vad_chunk(websocket, frame, stream_sid)


async def process_vad_chunk(websocket, frame_bytes: bytes, stream_sid: str):
    state = connections[websocket]

    audio = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32)
    rms = np.sqrt(np.mean(audio**2)) / 32768.0

    if rms < 0.012:  # Increased RMS threshold to filter noise
        state.speech_prob = 0.0
    else:
        tensor = torch.from_numpy(audio) / 32768.0
        with torch.no_grad():
            state.speech_prob = model(tensor, SAMPLE_RATE).item()
            # Only log when probability is high (voice likely detected)
            if state.speech_prob > 0.5:
                logger.debug(f"VAD prob: {state.speech_prob:.2f}")

    is_speech = state.speech_prob > VAD_CONFIDENCE_THRESHOLD
    state.vad_window.append(is_speech)

    state.pre_speech.append(frame_bytes)

    if not state.in_speech:
        if state.vad_window.count(True) >= TRIGGER_FRAMES:
            state.in_speech = True
            logger.info(f"🎤 Voice detected! (prob: {state.speech_prob:.2f})")
            state.current_utterance_id = start_tracking(
                websocket, stream_sid=stream_sid
            )
            for f in state.pre_speech:
                state.speech_buffer.extend(f)
            state.trailing_silence.clear()
        return

    state.speech_buffer.extend(frame_bytes)

    if is_speech:
        get_playback_state(websocket).cancel()
        await websocket.send_json(
            {"event": "barge_in", "confidence": state.speech_prob}
        )
        state.trailing_silence.clear()
        return

    state.trailing_silence.append(frame_bytes)

    if len(state.trailing_silence) < state.trailing_silence.maxlen:
        return

    if state.current_utterance_id:
        record_event(state.current_utterance_id, "VAD_END")

    if len(state.speech_buffer) >= MIN_UTTERANCE_BYTES:
        logger.info(f"🔚 Speech ended, sending {len(state.speech_buffer)} bytes to ASR")
        audio_16k = bytes(state.speech_buffer)  # Already 16kHz, no resampling needed
        record_event(state.current_utterance_id, "ASR_RECEIVED")
        await asr_queue.put((websocket, audio_16k, stream_sid))
    else:
        logger.debug(f"Speech too short ({len(state.speech_buffer)} bytes), ignoring")

    state.reset()
