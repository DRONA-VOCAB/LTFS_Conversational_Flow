"""
Handler for 'media' events from Smartflo.
Processes incoming audio chunks and integrates with VAANI queue pipeline.
"""

import logging
from fastapi import WebSocket

from ..schemas.incoming import MediaEvent
from ..core.session_manager import session_manager
from ..core.middleware import exception_handler
from ..audio.codec import decode_mulaw_from_base64
from ..audio.processor import process_incoming_audio

logger = logging.getLogger(__name__)


@exception_handler
async def handle_media(event: MediaEvent, websocket: WebSocket, **kwargs) -> None:
    """
    Handle the 'media' event from Smartflo.
    
    This event contains audio chunks from the caller.
    Flow:
    1. Decode base64 encoded μ-law audio
    2. Convert to PCM16 for processing
    3. Feed into ASR queue for speech recognition
    4. ASR → LLM → TTS pipeline processes automatically
    5. TTS response is sent back to Smartflo via the websocket
    
    Args:
        event: Validated MediaEvent object
        websocket: WebSocket connection
        **kwargs: Additional context
    """
    stream_sid = event.streamSid
    
    # Get the session
    session = await session_manager.get_session(stream_sid)
    if not session:
        logger.warning(f"Received media for unknown session: {stream_sid}")
        return
    
    # Decode base64 μ-law audio to PCM16
    try:
        payload = event.media.payload
        pcm_bytes = decode_mulaw_from_base64(payload)
        
        logger.debug(f"Decoded audio: {len(pcm_bytes)} PCM bytes for stream {stream_sid}")
        
        # Append to session buffer
        await session.append_audio(pcm_bytes)
        
        # Process the audio through VAANI queue pipeline
        # This will:
        # 1. Send to ASR for transcription
        # 2. ASR result goes to LLM for response
        # 3. LLM response goes to TTS for audio generation
        # 4. TTS sends audio back through websocket (needs integration below)
        await process_incoming_audio(pcm_bytes, stream_sid, websocket)
        
    except Exception as e:
        logger.error(f"Error processing media for stream {stream_sid}: {str(e)}", exc_info=True)
        raise
