"""
WebSocket Event Handlers
Handles specific event types received via WebSocket
"""

import asyncio
import logging
from typing import Dict
from fastapi import WebSocket

from services.llm_service import call_chatbot_init
from queues.tts_queue import tts_queue

logger = logging.getLogger(__name__)


async def handle_init_session(
    event: dict,
    websocket: WebSocket,
    websocket_id: str,
    connection_states: Dict,
    active_connections: Dict
):
    """Handle init_session event - Initialize conversation with customer"""
    customer_name = event.get("customer_name")
    state = connection_states.get(websocket_id)

    if not customer_name:
        error_msg = "Missing customer_name in init_session"
        logger.error(f"❌ {error_msg}")
        await websocket.send_json({"type": "error", "message": error_msg})
        return

    if not state:
        error_msg = "Invalid connection state"
        logger.error(f"❌ {error_msg}")
        await websocket.send_json({"type": "error", "message": error_msg})
        return

    logger.info(f"📞 Initializing session for: {customer_name}")

    try:
        # Call chatbot API to initialize session
        result = await call_chatbot_init(customer_name)

        chatbot_session_id = result.get("session_id")
        bot_response = result.get("bot_response", "")

        if chatbot_session_id:
            state["chatbot_session_id"] = chatbot_session_id
            state["customer_name"] = customer_name
            state["mic_enabled"] = True  # Enable mic after session init

            await websocket.send_json({
                "type": "session_initialized",
                "message": "Session initialized successfully",
                "chatbot_session_id": chatbot_session_id,
                "customer_name": customer_name
            })

            # Send initial greeting via TTS
            if bot_response:
                logger.info(f"📋 Sending initial greeting: {bot_response}")
                await tts_queue.put((websocket, bot_response, None, None))
        else:
            raise Exception("No session_id returned from chatbot API")

    except Exception as e:
        error_msg = f"Error initializing session: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        await websocket.send_json({"type": "error", "message": error_msg})


async def handle_tts_finished(
    event: dict,
    websocket: WebSocket,
    websocket_id: str,
    connection_states: Dict,
    active_connections: Dict
):
    """Handle tts_finished event - Called when TTS playback completes"""
    state = connection_states.get(websocket_id)

    if not state:
        logger.error(f"❌ No state found for websocket_id: {websocket_id}")
        return

    state["tts_playing"] = False

    # Check if conversation should end
    if state.get("pending_end"):
        state["pending_end"] = False
        logger.info("✅ Conversation completed, closing call")

        # Send status update for UI indicator
        await websocket.send_json({
            "type": "status_update",
            "status": "survey_completed",
            "message": "Survey completed"
        })

        # Give enough delay to ensure TTS audio finishes playing on client
        # The client may have buffered audio that takes time to play
        await asyncio.sleep(3.0)

        # Send call ended message
        await websocket.send_json({
            "type": "call_ended",
            "message": "Call ended successfully"
        })

        # Small delay before closing to ensure message is received
        await asyncio.sleep(0.5)

        # Close the WebSocket connection to end the call
        await websocket.close(code=1000, reason="Call ended")
        return

    # Notify client that TTS finished (mic always stays active)
    logger.info(f"✅ TTS finished for {websocket_id}")
    await websocket.send_json({
        "type": "tts_playback_finished",
        "message": "TTS playback completed"
    })


async def handle_tts_started(
    event: dict,
    websocket: WebSocket,
    websocket_id: str,
    connection_states: Dict,
    active_connections: Dict
):
    """Handle tts_started event - Called when TTS playback starts"""
    state = connection_states.get(websocket_id)
    if state:
        state["tts_playing"] = True
        logger.info(f"🔊 TTS started for {websocket_id} (barge-in enabled)")


async def handle_tts_request(
    event: dict,
    websocket: WebSocket,
    websocket_id: str,
    connection_states: Dict,
    active_connections: Dict
):
    """Handle manual TTS request"""
    text = event.get("text")
    if text:
        await tts_queue.put((websocket, text, None, None))
    else:
        logger.warning("TTS request received without text")


async def handle_ping(
    event: dict,
    websocket: WebSocket,
    websocket_id: str,
    connection_states: Dict,
    active_connections: Dict
):
    """Handle ping event - Respond with pong"""
    await websocket.send_json({"type": "pong"})
