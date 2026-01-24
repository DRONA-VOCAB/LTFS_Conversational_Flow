"""
Session manager for maintaining per-stream state.
"""

import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class Session:
    """
    Represents a single call/stream session.
    Maintains state for a specific streamSid.
    """
    
    def __init__(self, stream_sid: str, call_sid: str):
        self.stream_sid = stream_sid
        self.call_sid = call_sid
        self.sequence_counter = 0
        self.audio_buffer = bytearray()
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.metadata: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
    
    def next_sequence(self) -> int:
        """
        Get the next sequence number for this session.
        Ensures monotonic increment.
        
        Returns:
            Next sequence number
        """
        self.sequence_counter += 1
        self.last_activity = datetime.utcnow()
        return self.sequence_counter
    
    async def append_audio(self, audio_data: bytes) -> None:
        """
        Append audio data to the session buffer.
        
        Args:
            audio_data: Audio bytes to append
        """
        async with self._lock:
            self.audio_buffer.extend(audio_data)
            self.last_activity = datetime.utcnow()
    
    async def get_audio_buffer(self) -> bytes:
        """
        Get a copy of the current audio buffer.
        
        Returns:
            Copy of the audio buffer
        """
        async with self._lock:
            return bytes(self.audio_buffer)
    
    async def clear_audio_buffer(self) -> None:
        """Clear the audio buffer."""
        async with self._lock:
            self.audio_buffer.clear()
            self.last_activity = datetime.utcnow()
    
    def update_metadata(self, **kwargs) -> None:
        """
        Update session metadata.
        
        Args:
            **kwargs: Metadata key-value pairs
        """
        self.metadata.update(kwargs)
        self.last_activity = datetime.utcnow()
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get metadata value.
        
        Args:
            key: Metadata key
            default: Default value if key not found
            
        Returns:
            Metadata value or default
        """
        return self.metadata.get(key, default)


class SessionManager:
    """
    Manages multiple sessions across different streams.
    Thread-safe and async-safe.
    """
    
    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._lock = asyncio.Lock()
    
    async def create_session(self, stream_sid: str, call_sid: str) -> Session:
        """
        Create a new session.
        
        Args:
            stream_sid: Stream session identifier
            call_sid: Call session identifier
            
        Returns:
            New Session instance
        """
        async with self._lock:
            if stream_sid in self._sessions:
                logger.warning(f"Session {stream_sid} already exists, returning existing")
                return self._sessions[stream_sid]
            
            session = Session(stream_sid, call_sid)
            self._sessions[stream_sid] = session
            logger.info(f"Created new session: {stream_sid} (call: {call_sid})")
            return session
    
    async def get_session(self, stream_sid: str) -> Optional[Session]:
        """
        Get an existing session.
        
        Args:
            stream_sid: Stream session identifier
            
        Returns:
            Session instance or None if not found
        """
        async with self._lock:
            return self._sessions.get(stream_sid)
    
    async def delete_session(self, stream_sid: str) -> bool:
        """
        Delete a session.
        
        Args:
            stream_sid: Stream session identifier
            
        Returns:
            True if session was deleted, False if not found
        """
        async with self._lock:
            if stream_sid in self._sessions:
                del self._sessions[stream_sid]
                logger.info(f"Deleted session: {stream_sid}")
                return True
            return False
    
    async def get_all_sessions(self) -> Dict[str, Session]:
        """
        Get all active sessions.
        
        Returns:
            Dictionary of stream_sid -> Session
        """
        async with self._lock:
            return self._sessions.copy()
    
    async def cleanup_inactive_sessions(self, timeout_seconds: int = 3600) -> int:
        """
        Clean up sessions that have been inactive for too long.
        
        Args:
            timeout_seconds: Inactivity timeout in seconds
            
        Returns:
            Number of sessions cleaned up
        """
        async with self._lock:
            now = datetime.utcnow()
            to_delete = []
            
            for stream_sid, session in self._sessions.items():
                inactive_time = (now - session.last_activity).total_seconds()
                if inactive_time > timeout_seconds:
                    to_delete.append(stream_sid)
            
            for stream_sid in to_delete:
                del self._sessions[stream_sid]
                logger.info(f"Cleaned up inactive session: {stream_sid}")
            
            return len(to_delete)


# Global session manager instance
session_manager = SessionManager()
