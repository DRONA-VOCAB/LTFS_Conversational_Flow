"""
Incoming event schemas for Smartflo → Vendor communication.
These are events that Smartflo sends to the Vendor WebSocket server.
"""

from typing import Optional, Literal, Union
from pydantic import BaseModel, Field, validator


class MediaData(BaseModel):
    """Media payload data structure"""
    payload: str = Field(..., description="Base64 encoded μ-law audio data")
    chunk: int = Field(..., description="Chunk identifier")
    timestamp: int = Field(..., description="Timestamp of the media")


class StartData(BaseModel):
    """Start event data structure"""
    callSid: str = Field(..., description="Unique call session identifier")
    streamSid: str = Field(..., description="Unique stream session identifier")
    accountSid: Optional[str] = Field(None, description="Account identifier")
    tracks: Optional[str] = Field(None, description="Audio track configuration")
    customParameters: Optional[dict] = Field(None, description="Additional custom parameters")
    mediaFormat: Optional[dict] = Field(None, description="Media format specifications")


class StopData(BaseModel):
    """Stop event data structure"""
    callSid: str = Field(..., description="The Call identifier that started the Stream")
    reason: str = Field(..., description="The reason for ending the Stream.")
    accountSid: Optional[str] = Field(None, description="The Account identifier that created the Stream")


class DTMFData(BaseModel):
    """DTMF event data structure"""
    callSid: str = Field(..., description="Unique call session identifier")
    streamSid: str = Field(..., description="Unique stream session identifier")
    digit: str = Field(..., description="DTMF digit pressed")
    track: Optional[str] = Field(None, description="Audio track")


class MarkData(BaseModel):
    """Mark event data structure (Smartflo → Vendor)"""
    callSid: Optional[str] = Field(None, description="Unique call session identifier")
    streamSid: Optional[str] = Field(None, description="Unique stream session identifier")
    name: str = Field(..., description="Mark identifier/name")


# Base incoming event model
class BaseIncomingEvent(BaseModel):
    """Base model for all incoming events"""
    event: str = Field(..., description="Event type")
    sequenceNumber: int = Field(..., description="Sequence number for ordering")
    streamSid: str = Field(..., description="Stream session identifier")


class StartEvent(BaseIncomingEvent):
    """Event received when a call/stream starts"""
    event: Literal["start"] = "start"
    start: StartData = Field(..., description="Start event specific data")


class MediaEvent(BaseIncomingEvent):
    """Event received with audio media chunks"""
    event: Literal["media"] = "media"
    media: MediaData = Field(..., description="Media payload data")


class StopEvent(BaseIncomingEvent):
    """Event received when call/stream stops"""
    event: Literal["stop"] = "stop"
    stop: StopData = Field(..., description="Stop event specific data")


class DTMFEvent(BaseIncomingEvent):
    """Event received when user presses DTMF keys"""
    event: Literal["dtmf"] = "dtmf"
    dtmf: DTMFData = Field(..., description="DTMF event specific data")


class MarkEvent(BaseIncomingEvent):
    """Mark event received from Smartflo"""
    event: Literal["mark"] = "mark"
    mark: MarkData = Field(..., description="Mark event specific data")


class ConnectedEvent(BaseModel):
    event: Literal["connected"] = "connected"


# Factory function for parsing incoming events
def parse_incoming_event(raw_json: dict) -> Union[ConnectedEvent,StartEvent, MediaEvent, StopEvent, DTMFEvent, MarkEvent]:
    """
    Factory function to parse raw JSON into appropriate Pydantic event model.
    
    Args:
        raw_json: Dictionary containing the event data
        
    Returns:
        Appropriate Pydantic model instance based on event type
        
    Raises:
        ValueError: If event type is unknown or validation fails
    """
    event_type = raw_json.get("event")
    if event_type == "connected":
        return ConnectedEvent(**raw_json)
    elif event_type == "start":
        return StartEvent(**raw_json)
    elif event_type == "media":
        return MediaEvent(**raw_json)
    elif event_type == "stop":
        return StopEvent(**raw_json)
    elif event_type == "dtmf":
        return DTMFEvent(**raw_json)
    elif event_type == "mark":
        return MarkEvent(**raw_json)
    else:
        raise ValueError(f"Unknown event type: {event_type}")
