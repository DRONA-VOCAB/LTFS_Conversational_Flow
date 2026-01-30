"""ASR Service - Handles speech-to-text transcription"""
import asyncio
import logging
from typing import Dict

import aiohttp

from config.settings import ASR_API_URL
from queues.asr_queue import asr_queue
from queues.llm_queue import llm_queue
from utils.latency_tracker import record_event, cleanup_tracking
from core.audio_utils import (
    ASR_AUDIO_DIR,
    prepare_audio_bytes,
    build_audio_url,
    save_audio_non_blocking,
    get_next_turn_id,
    pcm16_to_wav,
)

logger = logging.getLogger(__name__)


async def asr_service_consumer(websocket_id: str, active_connections: Dict, connection_states: Dict):
    """
    ASR service consumer - processes audio from queue and transcribes

    Args:
        websocket_id: WebSocket connection ID
        active_connections: Dict of active connections
        connection_states: Dict of connection states
    """
    logger.info(f"ASR consumer started for {websocket_id}")

    async with aiohttp.ClientSession() as session:
        while websocket_id in active_connections:
            try:
                try:
                    item = await asyncio.wait_for(asr_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                websocket, audio_bytes, utterance_id = item

                # Check if this is for our connection
                if websocket != active_connections.get(websocket_id):
                    await asr_queue.put(item)
                    continue

                state = connection_states.get(websocket_id)
                if not state:
                    continue

                state["processing_asr"] = True
                logger.info(f"🔍 ASR: Processing {len(audio_bytes)} bytes for {websocket_id}")

                # Convert PCM to WAV
                wav_data = pcm16_to_wav(audio_bytes)

                # Prepare API request
                form_data = aiohttp.FormData()
                form_data.add_field("file", wav_data, filename="audio.wav", content_type="audio/wav")

                # Call ASR API
                async with session.post(ASR_API_URL, data=form_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        transcription = result.get("transcription", "").strip()
                        logger.info(f"📝 ASR Transcript: '{transcription}'")

                        if utterance_id:
                            record_event(utterance_id, "ASR_COMPLETE")

                        if transcription:
                            # Generate turn ID and save audio
                            turn_id = get_next_turn_id(state, state.get("chatbot_session_id") or websocket_id)
                            state["current_turn_id"] = turn_id

                            asr_file = f"{turn_id}_asr.wav"
                            audio_bytes_wav = prepare_audio_bytes(audio_bytes)
                            save_audio_non_blocking(ASR_AUDIO_DIR / asr_file, audio_bytes_wav)

                            # Build URL and store in state
                            asr_url = build_audio_url("asr_audios", asr_file)
                            state["last_asr_audio_url"] = asr_url
                            state["last_transcription"] = transcription

                            # Send transcription to client
                            await websocket.send_json({
                                "type": "transcription",
                                "text": transcription,
                                "detected_language": result.get("detected_language"),
                                "language_confidence": result.get("language_confidence"),
                            })

                            # Send to LLM queue
                            await llm_queue.put((websocket, transcription, utterance_id))
                        else:
                            logger.warning("ASR returned empty transcription")
                    else:
                        error_text = await response.text()
                        logger.error(f"ASR API failed with status {response.status}: {error_text}")

                # Reset state
                state["processing_asr"] = False

                if utterance_id:
                    cleanup_tracking(utterance_id)

                asr_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ASR consumer: {e}", exc_info=True)
                state = connection_states.get(websocket_id)
                if state:
                    state["processing_asr"] = False
