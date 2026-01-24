"""
Audio processor module integrated with VAANI queue system.
Integrates Smartflo with existing ASR → LLM → TTS pipeline.
"""

import logging
from typing import Optional
from fastapi import WebSocket

from services import process_frame

logger = logging.getLogger(__name__)


async def process_incoming_audio(
    pcm_bytes: bytes, 
    stream_sid: str, 
    websocket: WebSocket = None
) -> None:
    """
    Process incoming audio from Smartflo through the VAANI queue pipeline.
    
    This integrates Smartflo audio with the existing queue-based architecture:
    1. Audio → ASR queue (for speech recognition)
    2. ASR → LLM queue (for response generation)
    3. LLM → TTS queue (for audio response)
    4. TTS → Smartflo (via send_audio_response)
    
    Args:
        pcm_bytes: PCM16 encoded audio bytes
        stream_sid: Stream session identifier for context
        websocket: WebSocket connection (optional, for sending responses)
    """
    logger.debug(f"Processing {len(pcm_bytes)} bytes of PCM audio for stream {stream_sid}")
    
    # Import queues here to avoid circular dependencies
    try:

        if websocket:
            # Put audio into ASR queue for processing through the pipeline
            # Use stream_sid as utterance_id for tracking
            # await asr_queue.put((websocket, pcm_bytes, stream_sid))
            await process_frame(websocket, pcm_bytes,stream_sid)
            # logger.info(f"Smartflo audio ({len(pcm_bytes)} bytes) queued for ASR processing")
        else:
            logger.warning(f"No websocket provided for stream {stream_sid}, skipping queue")
    except ImportError as e:
        logger.error(f"Failed to import ASR queue: {e}")
    except Exception as e:
        logger.error(f"Error queuing audio for ASR: {e}", exc_info=True)


async def generate_response_audio(text: str, stream_sid: str) -> Optional[bytes]:
    """
    Generate audio response from text using existing TTS service.
    
    Note: This function is not directly used in the queue-based flow.
    Instead, the TTS service consumer handles audio generation and
    sends it back through the websocket.
    
    Args:
        text: Text to convert to speech
        stream_sid: Stream session identifier for context
        
    Returns:
        PCM16 encoded audio bytes, or None if generation fails
    """
    logger.debug(f"Generating audio response for text: '{text}' (stream: {stream_sid})")
    
    # In the queue-based architecture, TTS happens automatically
    # through the tts_service_consumer, which reads from tts_queue
    # and sends audio back through the websocket
    
    # This function exists for direct TTS calls if needed
    # For now, return None as TTS is handled by the queue system
    return None
