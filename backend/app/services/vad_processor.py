"""Voice Activity Detection (VAD) processor using Silero VAD"""
import time
import collections
import numpy as np
import logging
import torch
import torch.hub

from queues.asr_queue import asr_queue
from utils.latency_tracker import start_tracking, record_event

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================================================
# AUDIO CONSTANTS
# =========================================================
SAMPLE_RATE = 16000
FRAME_DURATION_MS = 32
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)
FRAME_BYTES = FRAME_SAMPLES * 2  # int16

# =========================================================
# LOAD SILERO VAD (ONCE)
# =========================================================
try:
    model, utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        force_reload=False
    )
    model.eval()
    vad_model_loaded = True
    logger.info("✅ Silero VAD loaded")
except Exception as e:
    logger.error(f"❌ Failed to load Silero VAD: {e}")
    vad_model_loaded = False
    model = None

# =========================================================
# NOISE-ROBUST TUNING (IMPORTANT)
# =========================================================
RMS_NOISE_GATE = 0.01          # 🔥 blocks fan/AC noise
STRONG_SPEECH_PROB = 0.85     # confident speech
WEAK_SPEECH_PROB = 0.50       # confident non-speech

# =========================================================
# DECISION WINDOW
# =========================================================
SPEECH_BUFFER_DURATION_MS = 480
SPEECH_BUFFER_FRAMES = SPEECH_BUFFER_DURATION_MS // FRAME_DURATION_MS

SPEECH_TRIGGER_RATIO = 0.90   # speech start
SPEECH_RELEASE_RATIO = 0.25   # speech end

# =========================================================
# UTTERANCE CONTROL
# =========================================================
MIN_UTTERANCE_DURATION_S = 1.2
MIN_UTTERANCE_SAMPLES = int(SAMPLE_RATE * MIN_UTTERANCE_DURATION_S)
MIN_UTTERANCE_BYTES = MIN_UTTERANCE_SAMPLES * 2  # 16-bit = 2 bytes per sample

PRE_SPEECH_MS = 400
PRE_SPEECH_FRAMES = PRE_SPEECH_MS // FRAME_DURATION_MS

TRAILING_SILENCE_MS = 700
TRAILING_SILENCE_FRAMES = TRAILING_SILENCE_MS // FRAME_DURATION_MS

# =========================================================
# STATE
# =========================================================
class VadState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.speech_buffer = bytearray()
        self.pre_speech_buffer = collections.deque(maxlen=PRE_SPEECH_FRAMES)
        self.vad_decision_buffer = collections.deque(maxlen=SPEECH_BUFFER_FRAMES)
        self.trailing_silence_buffer = collections.deque(maxlen=TRAILING_SILENCE_FRAMES)

        self.in_speech = False
        self.speech_start_time = None
        self.current_utterance_id = None


connections = {}


def cleanup_connection(websocket_id: str):
    """Clean up VAD state for disconnected client"""
    if websocket_id in connections:
        del connections[websocket_id]
        logger.info("🧹 VAD state cleaned for disconnected client")


# =========================================================
# MAIN FRAME PROCESSOR
# =========================================================
async def process_frame(websocket_id: str, frame_bytes: bytes, mic_enabled: bool = True):
    """Process audio frame through VAD - called continuously when mic is enabled"""
    """
    Process a single audio frame through VAD
    
    Args:
        websocket_id: Unique identifier for the WebSocket connection
        frame_bytes: Raw PCM audio bytes (16-bit, mono, 16kHz)
        mic_enabled: Whether microphone is enabled (should be False during TTS playback)
    """
    if not vad_model_loaded:
        return

    if websocket_id not in connections:
        connections[websocket_id] = VadState()

    state = connections[websocket_id]

    if len(frame_bytes) != FRAME_BYTES:
        logger.warning(f"Unexpected frame size {len(frame_bytes)}")
        return

    # Skip processing if mic is disabled (TTS is playing)
    if not mic_enabled:
        return

    # -----------------------------------------------------
    # Convert PCM → float
    # -----------------------------------------------------
    audio_np = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32)
    audio_f32 = audio_np / 32768.0

    # -----------------------------------------------------
    # RMS Noise Gate (CRITICAL)
    # -----------------------------------------------------
    rms = np.sqrt(np.mean(audio_f32 ** 2))
    if rms < RMS_NOISE_GATE:
        speech_prob = 0.0
    else:
        with torch.no_grad():
            speech_prob = model(
                torch.from_numpy(audio_f32),
                SAMPLE_RATE
            ).item()

    # -----------------------------------------------------
    # Probability-weighted decision (ANTI-NOISE)
    # -----------------------------------------------------
    if speech_prob > STRONG_SPEECH_PROB:
        is_speech = True
    elif speech_prob < WEAK_SPEECH_PROB:
        is_speech = False
    else:
        is_speech = False  # treat uncertain as noise

    # -----------------------------------------------------
    # Update rolling decision buffer
    # -----------------------------------------------------
    state.vad_decision_buffer.append(is_speech)
    speech_frames = state.vad_decision_buffer.count(True)
    total_frames = len(state.vad_decision_buffer)
    speech_ratio = speech_frames / total_frames if total_frames else 0.0

    # Always collect pre-speech audio
    state.pre_speech_buffer.append(frame_bytes)

    # =====================================================
    # STATE MACHINE
    # =====================================================
    # ---------------- SPEECH START ----------------
    if not state.in_speech:
        if (
            speech_ratio >= SPEECH_TRIGGER_RATIO and
            speech_frames >= int(0.6 * total_frames)
        ):
            state.in_speech = True
            state.speech_start_time = time.time()
            state.current_utterance_id = start_tracking(websocket_id)

            logger.info(f"🎙️ VAD: Speech started for {websocket_id} (utterance_id: {state.current_utterance_id})")

            # prepend pre-speech
            for f in state.pre_speech_buffer:
                state.speech_buffer.extend(f)

            state.speech_buffer.extend(frame_bytes)
            state.trailing_silence_buffer.clear()

    # ---------------- SPEECH CONTINUE ----------------
    else:
        state.speech_buffer.extend(frame_bytes)

        if speech_ratio < SPEECH_RELEASE_RATIO:
            state.trailing_silence_buffer.append(frame_bytes)

            if len(state.trailing_silence_buffer) == state.trailing_silence_buffer.maxlen:
                logger.info("🛑 <<< Speech ended (silence)")

                if state.current_utterance_id:
                    record_event(state.current_utterance_id, "VAD_END")

                if len(state.speech_buffer) >= MIN_UTTERANCE_BYTES:
                    duration_ms = (len(state.speech_buffer) / 2 / SAMPLE_RATE) * 1000
                    logger.info(
                        f"📤 VAD: Sending utterance to ASR queue for {websocket_id} "
                        f"(size: {len(state.speech_buffer)} bytes, duration: {duration_ms:.1f}ms, "
                        f"utterance_id: {state.current_utterance_id})"
                    )

                    if state.current_utterance_id:
                        record_event(state.current_utterance_id, "ASR_RECEIVED")

                    await asr_queue.put((
                        websocket_id,
                        bytes(state.speech_buffer),
                        state.current_utterance_id
                    ))
                    logger.info(f"✅ VAD: Utterance queued for ASR processing")
                else:
                    logger.warning(f"🗑️ VAD: Utterance too short ({len(state.speech_buffer)} bytes), discarded")

                state.reset()
        else:
            state.trailing_silence_buffer.clear()

