import logging
import time
import aiohttp
from dotenv import load_dotenv

from  config.settings import TTS_API_URL
from  queues.tts_queue import tts_queue
from services.playback_state import get_playback_state
from  utils.latency_tracker import record_and_report, record_event, latency_data

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- Audio framing constants ----
# 20 ms @ 16 kHz PCM16 = 320 samples = 640 bytes
PCM_FRAME_SIZE = 640


async def synthesize_stream(text: str):
    """
    Async generator that synthesizes text to speech and yields audio chunks.
    Used by websocket routes for direct TTS streaming.
    """
    logger.info(f"🎵 TTS: {text[:50]}...")

    async with aiohttp.ClientSession() as session:
        payload = {"text": text}

        try:
            async with session.post(TTS_API_URL, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"❌ TTS API error ({response.status}): {error_text}")
                    return

                chunk_count = 0
                async for chunk in response.content.iter_any():
                    if chunk:
                        chunk_count += 1
                        yield chunk

                logger.info(f"✅ TTS complete: {chunk_count} chunks")
        except Exception as e:
            logger.error(f"❌ Error in synthesize_stream: {e}", exc_info=True)


async def tts_service_consumer():
    """
    Pulls text from tts_queue, calls local TTS,
    and streams audio to Web UI clients (raw PCM stream)
    """

    logger.info("🎙️ Local TTS service consumer started")

    async with aiohttp.ClientSession() as session:
        while True:
            websocket, text, utterance_id = await tts_queue.get()

            try:
                logger.info(f"🗣️ Received text for TTS: {text}")

                await websocket.send_json(
                    {
                        "event": "tts_start",
                        "utterance_id": utterance_id,
                        "text": text,
                    }
                )

                payload = {"text": text}

                async with session.post(TTS_API_URL, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"TTS API error ({response.status}): {error_text}")
                        continue

                    playback = get_playback_state(websocket)
                    play_token = playback.new_token()

                    logger.info("🔊 Streaming TTS audio")
                    first_chunk_time = None

                    async for chunk in response.content.iter_any():
                        if not playback.is_valid(play_token):
                            logger.info("🛑 Barge-in detected — stopping TTS stream")
                            break
                        if not chunk:
                            continue

                        if first_chunk_time is None:
                            first_chunk_time = time.time()
                            record_event(utterance_id, "TTS_FIRST_CHUNK")

                            llm_finished = latency_data.get(utterance_id, {}).get(
                                "LLM_FINISHED"
                            )

                            if llm_finished:
                                delta = first_chunk_time - llm_finished
                                logger.info(f"⏱️ First TTS chunk latency: {delta:.3f}s")

                        try:
                            await websocket.send_bytes(chunk)
                        except Exception as e:
                            logger.warning(f"⚠️ Client disconnected: {e}")
                            break

                    logger.info("✅ Finished streaming TTS audio")

                await websocket.send_json(
                    {"event": "end", "utterance_id": utterance_id}
                )

                await record_and_report(
                    websocket, utterance_id, "TTS_END", final_transcription=text
                )

            except Exception as e:
                logger.error(f"❌ Error in TTS consumer: {e}", exc_info=True)

            finally:
                tts_queue.task_done()
