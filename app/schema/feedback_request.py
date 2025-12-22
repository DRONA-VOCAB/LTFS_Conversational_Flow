"""Request schemas."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime


class CallInitiateRequest(BaseModel):
    """Request to initiate a call."""
    agreement_no: str = Field(..., description="Agreement number of the customer")
    contact_number: Optional[str] = Field(None, description="Contact number to call")


class AudioChunkRequest(BaseModel):
    """Request containing audio chunk from client."""
    call_id: str = Field(..., description="Unique call identifier")
    audio_data: bytes = Field(..., description="Audio chunk data")
    audio_format: str = Field(default="wav", description="Audio format (wav, mp3, etc.)")


class ConversationState(BaseModel):
    """Current state of the conversation."""
    step: str = Field(..., description="Current conversation step")
    customer_name: Optional[str] = None
    agreement_no: Optional[str] = None
    responses: dict = Field(default_factory=dict)
    is_compliant: Optional[bool] = None
    call_started_at: Optional[datetime] = None


class TextMessageRequest(BaseModel):
    """Request for text-to-text conversation."""
    call_id: str = Field(..., description="Unique call identifier")
    text: str = Field(..., description="User's text message")

