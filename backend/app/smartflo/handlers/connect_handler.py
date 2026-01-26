"""
Handler for 'start' events from Smartflo.
Registers new session and extracts metadata.
"""
import asyncio
import logging

from fastapi import WebSocket

from core.websocket_handler import process_asr_queue, process_tts_queue, get_websocket_id
from ..core.middleware import exception_handler
from ..schemas.incoming import ConnectedEvent

logger = logging.getLogger(__name__)


@exception_handler
async def handle_connect(event: ConnectedEvent, websocket: WebSocket, **kwargs) -> None:
    """
    Handle the 'connected' event from Smartflo.

    This event is received immediately after the WebSocket connection is established.
    We need to:
    1. Acknowledge the connection
    2. Prepare for subsequent events

    Args:
        event: Validated ConnectedEvent object
        websocket: WebSocket connection
        **kwargs: Additional context
    """
    websocket_id = get_websocket_id(websocket)
    logger.info(f"Handshake with smartflo for connection established: {websocket.client} with event: {event.event}")
    asr_processor_task = asyncio.create_task(process_asr_queue(websocket_id))
    tts_processor_task = asyncio.create_task(process_tts_queue(websocket_id))
    # timeout_monitor_task = asyncio.create_task(monitor_timeout(websocket_id))
    logger.info(f"✅ Background tasks started for {websocket_id}")
    # Additional setup can be done here if needed
