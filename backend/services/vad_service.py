"""
Silero VAD (Voice Activity Detection) Service
Noise-robust real-time speech detection with decision buffering
Based on production-grade VAD implementation
"""

import time
import collections
import numpy as np
import logging
from typing import Optional, Dict, Any
from collections import deque

logger = logging.getLogger(__name__)

# Try to import torch
try:
    import torch
    import torch.hub

    TORCH_AVAILABLE = True
    logger.info("✅ PyTorch available")
except ImportError as e:
    TORCH_AVAILABLE = False
    logger.warning(f"⚠️ PyTorch not available: {e}. VAD will be disabled.")
    logger.warning("Install with: pip install torch")

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
vad_model_loaded = False
model = None
utils = None

if TORCH_AVAILABLE:
    try:
        model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad", model="silero_vad", force_reload=False
        )
        model.eval()
        vad_model_loaded = True
        logger.info("✅ Silero VAD loaded")
    except Exception as e:
        logger.error(f"❌ Failed to load Silero VAD: {e}", exc_info=True)
        vad_model_loaded = False
        model = None

# =========================================================
# NOISE-ROBUST TUNING (IMPORTANT)
# =========================================================
RMS_NOISE_GATE = 0.01  # 🔥 blocks fan/AC noise
STRONG_SPEECH_PROB = 0.85  # confident speech
WEAK_SPEECH_PROB = 0.50  # confident non-speech

# =========================================================
# DECISION WINDOW
# =========================================================
SPEECH_BUFFER_DURATION_MS = 480
SPEECH_BUFFER_FRAMES = SPEECH_BUFFER_DURATION_MS // FRAME_DURATION_MS

SPEECH_TRIGGER_RATIO = 0.90  # speech start
SPEECH_RELEASE_RATIO = 0.25  # speech end

# =========================================================
# UTTERANCE CONTROL
# =========================================================
MIN_UTTERANCE_DURATION_S = 1.2
MIN_UTTERANCE_SAMPLES = int(SAMPLE_RATE * MIN_UTTERANCE_DURATION_S)

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
        self.frames_processed = 0


# Global connections dictionary
connections = {}


def cleanup_connection(websocket):
    """Clean up VAD state for disconnected client"""
    if websocket in connections:
        del connections[websocket]
        logger.info("🧹 VAD state cleaned for disconnected client")


# =========================================================
# MAIN FRAME PROCESSOR
# =========================================================
async def process_frame(
    websocket,
    frame_bytes: bytes,
    on_speech_start: Optional[callable] = None,
    on_speech_end: Optional[callable] = None,
    on_no_speech: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Process a single audio frame through VAD

    Args:
        websocket: WebSocket connection
        frame_bytes: Raw PCM frame bytes (must be FRAME_BYTES length)
        on_speech_start: Callback when speech starts
        on_speech_end: Callback when speech ends (receives utterance bytes)
        on_no_speech: Callback when no speech detected

    Returns:
        Dict with detection results
    """
    if not vad_model_loaded:
        if on_no_speech:
            on_no_speech(frame_bytes, "vad_not_loaded")
        return {
            "is_speech": False,
            "probability": 0.0,
            "is_speaking": False,
            "error": "vad_not_loaded",
        }

    if websocket not in connections:
        connections[websocket] = VadState()

    state = connections[websocket]
    state.frames_processed += 1

    if len(frame_bytes) != FRAME_BYTES:
        logger.warning(
            f"⚠️ Unexpected frame size {len(frame_bytes)}, expected {FRAME_BYTES}"
        )
        # Try to pad or truncate
        if len(frame_bytes) < FRAME_BYTES:
            frame_bytes = frame_bytes + b"\x00" * (FRAME_BYTES - len(frame_bytes))
        else:
            frame_bytes = frame_bytes[:FRAME_BYTES]

    # -----------------------------------------------------
    # Convert PCM → float
    # -----------------------------------------------------
    audio_np = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32)
    audio_f32 = audio_np / 32768.0

    # -----------------------------------------------------
    # RMS Noise Gate (CRITICAL)
    # -----------------------------------------------------
    rms = np.sqrt(np.mean(audio_f32**2))
    if rms < RMS_NOISE_GATE:
        speech_prob = 0.0
        is_speech = False
    else:
        with torch.no_grad():
            speech_prob = model(torch.from_numpy(audio_f32), SAMPLE_RATE).item()

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
        if speech_ratio >= SPEECH_TRIGGER_RATIO and speech_frames >= int(
            0.6 * total_frames
        ):
            state.in_speech = True
            state.speech_start_time = time.time()
            state.current_utterance_id = f"utt_{int(time.time() * 1000)}"

            logger.info(
                f"🎙️ >>> Speech started (Frame {state.frames_processed}, "
                f"Prob={speech_prob:.3f}, Ratio={speech_ratio:.2f})"
            )

            # Call speech start callback
            if on_speech_start:
                try:
                    on_speech_start()
                except Exception as e:
                    logger.error(
                        f"Error in on_speech_start callback: {e}", exc_info=True
                    )

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

            if (
                len(state.trailing_silence_buffer)
                == state.trailing_silence_buffer.maxlen
            ):
                logger.info(
                    f"🛑 <<< Speech ended (silence) - Frame {state.frames_processed}, "
                    f"Utterance: {len(state.speech_buffer)} bytes"
                )

                if (
                    len(state.speech_buffer) >= MIN_UTTERANCE_SAMPLES * 2
                ):  # bytes = samples * 2
                    logger.info(
                        f"📤 Sending utterance to ASR "
                        f"({len(state.speech_buffer)} bytes)"
                    )

                    utterance_bytes = bytes(state.speech_buffer)

                    # Call speech end callback (async)
                    if on_speech_end:
                        try:
                            import asyncio

                            if asyncio.iscoroutinefunction(on_speech_end):
                                await on_speech_end(utterance_bytes)
                            else:
                                # If not async, create task
                                asyncio.create_task(on_speech_end(utterance_bytes))
                        except Exception as e:
                            logger.error(
                                f"Error in on_speech_end callback: {e}", exc_info=True
                            )
                else:
                    logger.warning(
                        f"🗑️ Utterance too short ({len(state.speech_buffer)} bytes), discarded"
                    )

                state.reset()
        else:
            state.trailing_silence_buffer.clear()

    # Return detection results
    return {
        "is_speech": is_speech,
        "probability": speech_prob,
        "is_speaking": state.in_speech,
        "speech_ratio": speech_ratio,
        "rms": rms,
        "frames_processed": state.frames_processed,
    }
