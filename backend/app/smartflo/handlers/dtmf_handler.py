"""
Handler for 'dtmf' events from Smartflo.
Processes DTMF key presses.
"""

import logging
from fastapi import WebSocket

from ..schemas.incoming import DTMFEvent
from ..core.session_manager import session_manager
from ..core.middleware import exception_handler

logger = logging.getLogger(__name__)


@exception_handler
async def handle_dtmf(event: DTMFEvent, websocket: WebSocket, **kwargs) -> None:
    """
    Handle the 'dtmf' event from Smartflo.
    
    This event is received when the caller presses a DTMF key.
    We can use this for:
    - IVR menu navigation
    - User input collection
    - Call control
    
    Args:
        event: Validated DTMFEvent object
        websocket: WebSocket connection
        **kwargs: Additional context
    """
    stream_sid = event.streamSid
    digit = event.dtmf.digit
    
    logger.info(f"Handling DTMF event for stream: {stream_sid}, digit: {digit}")
    
    # Get the session
    session = await session_manager.get_session(stream_sid)
    if not session:
        logger.warning(f"Received DTMF for unknown session: {stream_sid}")
        return
    
    # Store DTMF digit in session metadata
    dtmf_history = session.get_metadata("dtmf_history", [])
    dtmf_history.append(digit)
    session.update_metadata(dtmf_history=dtmf_history)
    
    logger.debug(f"DTMF history for {stream_sid}: {''.join(dtmf_history)}")
    
    # Process DTMF digit:
    # - Navigate IVR menu
    # - Collect user input (phone numbers, account numbers, etc.)
    # - Trigger specific actions
    # - etc.
    
    # Example: Simple menu navigation
    # if digit == "1":
    #     # Play option 1 audio
    #     pass
    # elif digit == "2":
    #     # Play option 2 audio
    #     pass
