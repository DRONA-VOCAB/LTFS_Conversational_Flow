"""
Handler for 'mark' events from Smartflo.
Processes mark events (acknowledgments of playback completion).
"""

import logging
from fastapi import WebSocket

from ..schemas.incoming import MarkEvent
from ..core.session_manager import session_manager
from ..core.middleware import exception_handler

logger = logging.getLogger(__name__)


@exception_handler
async def handle_mark(event: MarkEvent, websocket: WebSocket, **kwargs) -> None:
    """
    Handle the 'mark' event from Smartflo.
    
    This event is received as an acknowledgment that Smartflo has:
    - Finished playing audio to a specific mark
    - Processed a mark event we sent
    
    We can use this for:
    - Tracking playback progress
    - Synchronizing audio streams
    - Managing conversation flow
    
    Args:
        event: Validated MarkEvent object
        websocket: WebSocket connection
        **kwargs: Additional context
    """
    stream_sid = event.streamSid
    mark_name = event.mark.name
    
    logger.info(f"Handling mark event for stream: {stream_sid}, mark: {mark_name}")
    
    # Get the session
    session = await session_manager.get_session(stream_sid)
    if not session:
        logger.warning(f"Received mark for unknown session: {stream_sid}")
        return
    
    # Store mark in session metadata
    marks_received = session.get_metadata("marks_received", [])
    marks_received.append(mark_name)
    session.update_metadata(marks_received=marks_received)
    
    logger.debug(f"Marks received for {stream_sid}: {marks_received}")
    
    # Process mark:
    # - Track which audio segments have been played
    # - Trigger next action in conversation flow
    # - Send analytics
    # - etc.
