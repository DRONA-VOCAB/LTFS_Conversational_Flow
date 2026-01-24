"""
Helper module to send TTS audio responses back to Smartflo.
This bridges the TTS service output with Smartflo's WebSocket protocol.
"""

import logging
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


async def send_audio_to_smartflo(
        websocket: WebSocket,
        pcm16_frame: bytes,
        stream_sid: str
) -> None:
    """
    Sends ONE Smartflo media packet.

    Input:
      - 640 bytes PCM16 @ 16kHz (20ms)

    Output:
      - 160 bytes mulaw @ 8kHz (base64)
    """

    try:
        from smartflo.core.session_manager import session_manager
        from smartflo.audio import encode_pcm8_to_mulaw_base64, convert_to_8kHz
        from smartflo.websocket_server import smartflo_server

        # ---- Validate frame size ----
        if len(pcm16_frame) != 640:
            logger.warning(
                f"Dropping invalid PCM frame size: {len(pcm16_frame)}"
            )
            return

        session = await session_manager.get_session(stream_sid)
        if not session:
            logger.warning(f"Session {stream_sid} not found")
            return
        pcm8k = convert_to_8kHz(pcm16_frame, original_sample_rate=16000)
        base64_audio = encode_pcm8_to_mulaw_base64(pcm8k)

        seq = session.next_sequence()

        await smartflo_server.send_media_event(
            websocket=websocket,
            stream_sid=stream_sid,
            sequence_number=seq,
            payload=base64_audio
        )

    except Exception as e:
        logger.error(
            f"Error sending audio to Smartflo: {e}",
            exc_info=True
        )


def is_smartflo_connection(websocket: WebSocket) -> bool:
    """
    Check if a websocket connection is from Smartflo.
    
    We can identify Smartflo connections by checking if they have
    an associated session in the Smartflo session manager.
    
    Args:
        websocket: WebSocket connection to check
        
    Returns:
        True if this is a Smartflo connection, False otherwise
    """
    try:
        # Check if this websocket has any Smartflo sessions
        # by checking the websocket's path or other attributes
        if hasattr(websocket, 'scope'):
            path = websocket.scope.get('path', '')
            return '/vendor-stream' in path
        return False
    except Exception as e:
        logger.error(f"Error checking Smartflo connection: {e}")
        return False


async def get_stream_sid_for_websocket(websocket: WebSocket) -> Optional[str]:
    """
    Get the stream_sid associated with a websocket connection.
    
    This searches through active Smartflo sessions to find the
    stream_sid for a given websocket.
    
    Args:
        websocket: WebSocket connection
        
    Returns:
        stream_sid if found, None otherwise
    """
    try:
        from smartflo.core.session_manager import session_manager

        # Get all active sessions
        all_sessions = await session_manager.get_all_sessions()

        # Find session by websocket (we need to store websocket in session)
        # For now, we'll use the utterance_id which is the stream_sid
        # This is a limitation - we need to pass stream_sid through the queue

        # Note: This is a workaround. Ideally, we should store the websocket
        # reference in the session or pass stream_sid through the queue system

        return None  # Will be handled by using stream_sid as utterance_id

    except Exception as e:
        logger.error(f"Error getting stream_sid: {e}")
        return None
