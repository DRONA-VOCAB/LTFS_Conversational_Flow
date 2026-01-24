"""
Handler for 'start' events from Smartflo.
Registers new session and extracts metadata.
"""

import logging

from fastapi import WebSocket
from ..core.middleware import exception_handler
from ..core.session_manager import session_manager
from ..schemas.incoming import StartEvent

logger = logging.getLogger(__name__)


@exception_handler
async def handle_start(event: StartEvent, websocket: WebSocket, **kwargs) -> None:
    """
    Handle the 'start' event from Smartflo.
    
    This event is received when a new call/stream begins.
    We need to:
    1. Create a new session
    2. Extract and store metadata
    3. Prepare audio engine (if needed)
    
    Note: Smartflo doesn't expect immediate audio response after start event.
    
    Args:
        event: Validated StartEvent object
        websocket: WebSocket connection
        **kwargs: Additional context
    """
    logger.info(f"Handling start event for stream: {event.streamSid}")

    # Extract metadata from start event
    call_sid = event.start.callSid
    stream_sid = event.streamSid
    account_sid = event.start.accountSid
    tracks = event.start.tracks
    custom_params = event.start.customParameters
    media_format = event.start.mediaFormat

    # Create a new session
    session = await session_manager.create_session(stream_sid, call_sid)

    # Store metadata in session
    session.update_metadata(
        account_sid=account_sid,
        tracks=tracks,
        custom_parameters=custom_params,
        media_format=media_format,
    )

    logger.info(f"Session created: {stream_sid} (call: {call_sid})")
    logger.debug(f"Session metadata: {session.metadata}")

    welcome_text = "Welcome to Vaani A.I assistance"
    logger.info(f"sending welcome audio to stream_id:: {stream_sid} : {welcome_text})")
    # ask @Nancy  and @Sneha : what happens when call connects?

    # Additional initialization can be done here:
    # - Initialize ASR engine
    # - Setup TTS service
    # - Load conversation context
    # - etc.
