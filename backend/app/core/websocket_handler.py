"""
WebSocket Handler - Main WebSocket connection handler
Simplified and modular architecture
"""

import asyncio
import json
import logging
from typing import Dict
from fastapi import WebSocket, WebSocketDisconnect

from core.router import router
from core.event_handlers import (
    handle_init_session,
    handle_tts_finished,
    handle_tts_started,
    handle_tts_request,
    handle_ping,
)
from services.asr_service import asr_service_consumer
from services.llm_service import llm_service_consumer
from services.tts_service import tts_service_consumer
from services.vad_silero import process_frame, cleanup_connection

logger = logging.getLogger(__name__)

# Track active connections and their states
active_connections: Dict[str, WebSocket] = {}
connection_states: Dict[str, Dict] = {}


# Register event handlers with router
_HANDLERS = {
    "init_session": handle_init_session,
    "tts_finished": handle_tts_finished,
    "tts_started": handle_tts_started,
    "tts_request": handle_tts_request,
    "ping": handle_ping,
}

for event_name, handler in _HANDLERS.items():
    async def _handler(event: dict, websocket: WebSocket, handler=handler, **kwargs):
        await handler(event, websocket, kwargs.get("websocket_id"), connection_states, active_connections)
    router.route(event_name)(_handler)


def get_websocket_id(websocket: WebSocket) -> str:
    """Get or create a unique ID for the WebSocket connection"""
    if not hasattr(websocket, "_id"):
        websocket._id = id(websocket)
    return str(websocket._id)


def init_connection_state(websocket_id: str) -> None:
    """Initialize state for new connection"""
    connection_states[websocket_id] = {
        "mic_enabled": True,  # Mic always enabled, barge-in supported
        "chatbot_session_id": None,
        "tts_playing": False,
        "processing_asr": False,
        "customer_name": None,
        "turn_counter": 0,
        "pending_end": False,
    }


async def process_text_event(websocket: WebSocket, websocket_id: str, text: str):
    """Process text message from client"""
    try:
        event_data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON received: {e}")
        await websocket.send_json({"type": "error", "message": "Invalid JSON"})
        return

    event_type = event_data.get("type")
    if not event_type:
        await websocket.send_json({"type": "error", "message": "Missing 'type' field"})
        return

    if router.get_handler(event_type):
        try:
            await router.dispatch(event_data, websocket, websocket_id=websocket_id)
        except Exception as e:
            logger.error(f"❌ Handler error {event_type}: {e}", exc_info=True)
            await websocket.send_json({"type": "error", "message": f"Handler error: {str(e)}"})
    else:
        await websocket.send_json({"type": "error", "message": f"No handler for: {event_type}"})


async def process_audio_bytes(websocket_id: str, audio_data: bytes):
    """Process binary audio frame - always processes (barge-in enabled)"""
    state = connection_states[websocket_id]
    # Only skip if already processing ASR (to avoid duplicate processing)
    if not state.get("processing_asr"):
        await process_frame(
            active_connections[websocket_id], audio_data, stream_sid=websocket_id
        )


async def cleanup_tasks(tasks: tuple):
    """Cancel and cleanup background tasks"""
    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def websocket_audio_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for audio streaming"""
    logger.info("🔌 WebSocket connection")
    await websocket.accept()

    websocket_id = get_websocket_id(websocket)
    active_connections[websocket_id] = websocket
    init_connection_state(websocket_id)
    logger.info(f"✅ WebSocket connected: {websocket_id}")

    try:
        # Start background processors
        tasks = (
            asyncio.create_task(asr_service_consumer(websocket_id, active_connections, connection_states)),
            asyncio.create_task(llm_service_consumer(websocket_id, active_connections, connection_states)),
            asyncio.create_task(tts_service_consumer(websocket_id, active_connections, connection_states)),
        )

        await websocket.send_json({
            "type": "websocket_ready",
            "message": "WebSocket ready, waiting for init_session",
        })

        # Main message loop
        while True:
            try:
                message = await websocket.receive()

                if "text" in message:
                    await process_text_event(websocket, websocket_id, message["text"])
                elif "bytes" in message:
                    await process_audio_bytes(websocket_id, message["bytes"])

            except WebSocketDisconnect:
                logger.info(f"❌ Disconnected: {websocket_id}")
                break
            except RuntimeError as e:
                # Starlette raises RuntimeError('Cannot call "receive" once a disconnect message has been received.')
                # Handle cleanly without noisy stacktrace.
                logger.info(f"Receive loop ended for {websocket_id}: {e}")
                break
            except Exception as e:
                logger.error(f"Error in loop: {e}", exc_info=True)
                break

    finally:
        cleanup_connection(websocket)
        active_connections.pop(websocket_id, None)
        connection_states.pop(websocket_id, None)
        await cleanup_tasks(tasks)
        logger.info(f"🧹 Cleaned up: {websocket_id}")
