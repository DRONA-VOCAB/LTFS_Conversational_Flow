"""
TTS Service - Handles text-to-speech synthesis
Combines API calls and queue processing with audio saving
"""

import asyncio
import logging
from typing import Dict
import aiohttp

from config.settings import TTS_API_URL
from queues.tts_queue import tts_queue
from services.google_sheet_logger import log_interaction
from utils.latency_tracker import record_event, cleanup_tracking
from core.audio_utils import (
    TTS_AUDIO_DIR,
    prepare_audio_bytes,
    build_audio_url,
    save_audio_non_blocking,
    sanitize_session_id,
)

logger = logging.getLogger(__name__)


async def synthesize_stream(text: str):
    """Async generator that synthesizes text to speech and yields audio chunks"""
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


async def tts_service_consumer(websocket_id: str, active_connections: Dict, connection_states: Dict):
    """Process TTS queue - synthesize text to speech and stream audio"""
    logger.info(f"TTS consumer started for {websocket_id}")
    while websocket_id in active_connections:
        try:
            try:
                item = await asyncio.wait_for(tts_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            # Support both 3-tuple and 4-tuple formats
            if len(item) == 4:
                websocket, text, utterance_id, audio_base = item
            else:
                websocket, text, utterance_id = item
                audio_base = None

            # Check if this is for our connection
            if websocket != active_connections.get(websocket_id):
                await tts_queue.put(item)
                continue

            state = connection_states.get(websocket_id)
            if state:
                state["tts_playing"] = True

            logger.info(f"🗣️ TTS: Playing '{text[:50]}...' (barge-in enabled)")

            # Send bot message to client
            await websocket.send_json({"type": "bot_message", "text": text})
            await websocket.send_json({"type": "tts_start", "text": text})

            # Stream TTS audio
            chunk_count = 0
            audio_buffer = bytearray()
            async for audio_chunk in synthesize_stream(text):
                if audio_chunk:
                    audio_buffer.extend(audio_chunk)
                    await websocket.send_bytes(audio_chunk)
                    chunk_count += 1

            await websocket.send_json({"type": "tts_end", "chunks_sent": chunk_count})
            logger.info(f"✅ TTS complete: {chunk_count} chunks sent")

            # Save TTS audio file
            if audio_buffer and state:
                turn_id = audio_base or state.get("current_turn_id") or sanitize_session_id(
                    state.get("chatbot_session_id") or websocket_id
                )
                tts_file = f"{turn_id}_tts.wav"
                audio_bytes = prepare_audio_bytes(bytes(audio_buffer))
                save_audio_non_blocking(TTS_AUDIO_DIR / tts_file, audio_bytes)

                tts_url = build_audio_url("tts_audios", tts_file)
                state["last_tts_audio_url"] = tts_url

                # Log interaction to Google Sheets
                await _log_interaction(websocket_id, text, tts_url, connection_states)

            # Reset state
            if state:
                state["tts_playing"] = False

            if utterance_id:
                record_event(utterance_id, "TTS_COMPLETE")
                cleanup_tracking(utterance_id)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error processing TTS: {e}", exc_info=True)
            state = connection_states.get(websocket_id)
            if state:
                state["tts_playing"] = False

    logger.info(f"TTS consumer stopped for {websocket_id}")


async def _log_interaction(websocket_id: str, bot_response: str, tts_url: str, connection_states: Dict):
    """Log interaction to Google Sheets"""
    state = connection_states.get(websocket_id)
    if not state:
        return

    asr_url = state.get("last_asr_audio_url")
    transcription = state.get("last_transcription")
    session_id = state.get("chatbot_session_id") or f"ws_{websocket_id}"

    if asr_url and transcription and tts_url:
        payload = {
            "session_id": session_id,
            "asr_audio_url": asr_url,
            "transcription": transcription,
            "llm_response": bot_response,
            "tts_audio_url": tts_url,
        }
        asyncio.create_task(log_interaction(payload))
