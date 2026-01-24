"""
Handler for 'stop' events from Smartflo.
Cleans up session and resources.
"""

import logging
from fastapi import WebSocket

from ..schemas.incoming import StopEvent
from ..core.session_manager import session_manager
from ..core.middleware import exception_handler

logger = logging.getLogger(__name__)


@exception_handler
async def handle_stop(event: StopEvent, websocket: WebSocket, **kwargs) -> None:
    """
    Handle the 'stop' event from Smartflo.
    
    This event is received when a call/stream ends.
    We need to:
    1. Clean up session resources
    2. Close audio engines
    3. Save any necessary data
    4. Remove session from manager
    
    Args:
        event: Validated StopEvent object
        websocket: WebSocket connection
        **kwargs: Additional context
    """
    stream_sid = event.streamSid
    call_sid = event.stop.callSid
    
    logger.info(f"Handling stop event for stream: {stream_sid} (call: {call_sid})")
    
    # Get the session before deleting
    session = await session_manager.get_session(stream_sid)
    if session:
        # Log session statistics
        audio_buffer_size = len(session.audio_buffer)
        logger.info(f"Session {stream_sid} stats: {audio_buffer_size} bytes in buffer, "
                   f"{session.sequence_counter} events processed")
        
        # Clean up resources
        await session.clear_audio_buffer()
        
        # Additional cleanup can be done here:
        # - Save conversation data
        # - Close ASR/TTS connections
        # - Send analytics
        # - etc.
        
        # Delete the session
        deleted = await session_manager.delete_session(stream_sid)
        if deleted:
            logger.info(f"Session {stream_sid} successfully deleted")
        else:
            logger.warning(f"Failed to delete session {stream_sid}")
    else:
        logger.warning(f"Received stop event for unknown session: {stream_sid}")
