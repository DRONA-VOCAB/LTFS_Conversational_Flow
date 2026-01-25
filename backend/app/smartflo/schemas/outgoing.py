"""
Outgoing event schemas for Vendor → Smartflo communication.
These are events that the Vendor WebSocket server sends to Smartflo.
"""

from typing import Optional, Literal, Any, Dict
from pydantic import BaseModel, Field


class BaseOutgoingEvent(BaseModel):
    """Base model for all outgoing events"""
    event: str = Field(..., description="Event type")
    sequenceNumber: Optional[int] = Field(None, description="Sequence number for ordering")
    streamSid: Optional[str] = Field(None, description="Stream session identifier")


class VendorMediaData(BaseModel):
    """Vendor media payload data structure"""
    payload: str = Field(..., description="Base64 encoded μ-law audio data")
    chunk: Optional[str] = Field(None, description="Chunk identifier")
    timestamp: Optional[str] = Field(None, description="Timestamp of the media")


class VendorMediaEvent(BaseOutgoingEvent):
    """Event sent to stream audio back to Smartflo"""
    event: Literal["media"] = "media"
    streamSid: str = Field(..., description="Stream session identifier")
    sequenceNumber: int = Field(..., description="Sequence number for ordering")
    media: VendorMediaData = Field(..., description="Media payload data")


class ClearEvent(BaseOutgoingEvent):
    """Event sent to clear Smartflo's audio buffer"""
    event: Literal["clear"] = "clear"
    streamSid: str = Field(..., description="Stream session identifier")


class VendorMarkData(BaseModel):
    """Vendor mark data structure"""
    name: str = Field(..., description="Mark identifier/name")


class VendorMarkEvent(BaseOutgoingEvent):
    """Event sent after playback is finished or to mark specific points"""
    event: Literal["mark"] = "mark"
    streamSid: str = Field(..., description="Stream session identifier")
    sequenceNumber: int = Field(..., description="Sequence number for ordering")
    mark: VendorMarkData = Field(..., description="Mark data")


# Event Builder Pattern
class EventBuilder:
    """
    Builder pattern for constructing outgoing events.
    Provides a fluent interface for building Smartflo events.
    
    Example:
        event = (EventBuilder()
                .type("media")
                .sequence(1)
                .sid("ST123456")
                .payload(payload="base64data", chunk="1")
                .build())
    """
    
    def __init__(self):
        self._event_type: Optional[str] = None
        self._sequence_number: Optional[int] = None
        self._stream_sid: Optional[str] = None
        self._payload_data: Dict[str, Any] = {}
        self._extra_fields: Dict[str, Any] = {}
    
    def type(self, event_type: str) -> 'EventBuilder':
        """Set the event type"""
        self._event_type = event_type
        return self
    
    def sequence(self, n: int) -> 'EventBuilder':
        """Set the sequence number"""
        self._sequence_number = n
        return self
    
    def sid(self, stream_sid: str) -> 'EventBuilder':
        """Set the stream SID"""
        self._stream_sid = stream_sid
        return self
    
    def payload(self, **kwargs) -> 'EventBuilder':
        """Set payload data (for media, mark, etc.)"""
        self._payload_data.update(kwargs)
        return self
    
    def extra(self, **kwargs) -> 'EventBuilder':
        """Set additional fields"""
        self._extra_fields.update(kwargs)
        return self
    
    def build(self) -> dict:
        """
        Build and return the event as a dictionary.
        
        Returns:
            Dictionary representation of the event
            
        Raises:
            ValueError: If required fields are missing
        """
        if not self._event_type:
            raise ValueError("Event type is required")
        
        event_dict = {
            "event": self._event_type,
        }
        
        # Add sequence number if provided
        if self._sequence_number is not None:
            event_dict["sequenceNumber"] = self._sequence_number
        
        # Add stream SID if provided
        if self._stream_sid:
            event_dict["streamSid"] = self._stream_sid
        
        # Add event-specific payload
        if self._event_type == "connected":
            event_dict["protocol"] = self._payload_data.get("protocol", "Call")
            event_dict["version"] = self._payload_data.get("version", "1.0.0")
        
        elif self._event_type == "media":
            if "payload" not in self._payload_data:
                raise ValueError("Media event requires 'payload' in payload data")
            
            event_dict["media"] = {
                "payload": self._payload_data["payload"],
            }
            if "chunk" in self._payload_data:
                event_dict["media"]["chunk"] = self._payload_data["chunk"]
            if "timestamp" in self._payload_data:
                event_dict["media"]["timestamp"] = self._payload_data["timestamp"]
        
        elif self._event_type == "mark":
            if "name" not in self._payload_data:
                raise ValueError("Mark event requires 'name' in payload data")
            
            event_dict["mark"] = {
                "name": self._payload_data["name"]
            }
        
        elif self._event_type == "clear":
            # Clear event doesn't need additional payload
            pass
        
        # Add any extra fields
        event_dict.update(self._extra_fields)
        
        return event_dict
