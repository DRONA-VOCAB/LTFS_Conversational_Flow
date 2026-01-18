import io
import logging
import wave

import aiohttp

from  config.settings import ASR_API_URL
from  queues.asr_queue import asr_queue
from  queues.llm_queue import llm_queue
from  utils.latency_tracker import record_event

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Audio Parameters (match your ASR / WebRTC settings) ---
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit PCM = 2 bytes per sample


def pcm16_to_wav(pcm_bytes, sample_rate=SAMPLE_RATE, channels=CHANNELS):
    """
    Convert raw 16-bit PCM audio bytes into a valid WAV file (in-memory).
    """
    with io.BytesIO() as wav_buffer:
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return wav_buffer.getvalue()


async def transcribe_audio(audio_bytes: bytes) -> dict:
    """
    Transcribe audio bytes using ASR API.
    Returns dict with transcription and optional language info.
    """
    async with aiohttp.ClientSession() as session:
        # Convert PCM16 raw data → valid WAV
        wav_data = pcm16_to_wav(audio_bytes)

        # Prepare payload (sending raw bytes as file)
        form_data = aiohttp.FormData()
        form_data.add_field(
            "file", wav_data, filename="audio.wav", content_type="audio/wav"
        )

        # Call the ASR API
        async with session.post(ASR_API_URL, data=form_data) as response:
            if response.status == 200:
                result = await response.json()
                transcription = result.get("transcription", "").strip()
                return {
                    "transcription": transcription,
                    "detected_language": result.get("detected_language"),
                    "language_confidence": result.get("language_confidence"),
                }
            else:
                error_text = await response.text()
                logger.error(
                    f"ASR API request failed with status {response.status}: {error_text}"
                )
                return {"transcription": ""}


async def asr_service_consumer():
    """
    This consumer pulls audio data (file paths or bytes) from the asr_queue,
    sends it to the ASR REST API, and puts the transcribed text into the llm_queue.
    """
    logger.info("ASR service consumer started.")
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Get the next audio item
                websocket, audio_bytes, utterance_id = await asr_queue.get()
                logger.info(f"ASR received {len(audio_bytes)} bytes of audio data.")

                # Convert PCM16 raw data → valid WAV
                wav_data = pcm16_to_wav(audio_bytes)
                logger.info(
                    f"Converted {len(audio_bytes)} bytes PCM → {len(wav_data)} bytes WAV"
                )

                # --- Prepare payload (sending raw bytes as file) ---
                form_data = aiohttp.FormData()
                form_data.add_field(
                    "file", wav_data, filename="audio.wav", content_type="audio/wav"
                )

                # --- Call the ASR API ---
                async with session.post(ASR_API_URL, data=form_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        # transcription = result.get("text", "").strip()
                        transcription = result.get("transcription", "").strip()
                        logger.info(f"ASR transcription: {transcription}")

                        if transcription:
                            record_event(utterance_id, "ASR_FINISHED")
                            # Push to LLM queue for next step
                            await llm_queue.put(
                                (websocket, transcription, utterance_id)
                            )
                            await websocket.send_json(
                                {"event": "asr_final", "text": transcription}
                            )
                        else:
                            logger.warning("ASR returned empty transcription.")
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"ASR API request failed with status {response.status}: {error_text}"
                        )

            except Exception as e:
                logger.error(
                    f"Error in ASR service consumer ({e.__class__.__name__}): {e}"
                )

            # Mark the queue task as done
            asr_queue.task_done()
