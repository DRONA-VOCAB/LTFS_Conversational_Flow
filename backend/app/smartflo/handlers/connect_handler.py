"""
Handler for 'start' events from Smartflo.
Registers new session and extracts metadata.
"""

import logging

from fastapi import WebSocket

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
    logger.info(f"Handshake with smartflo for connection established: {websocket.client} with event: {event.event}")
    # Additional setup can be done here if needed
