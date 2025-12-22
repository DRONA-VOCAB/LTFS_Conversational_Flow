"""Response schemas."""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import base64


class CallStatusResponse(BaseModel):
    """Response for call status."""
    call_id: str
    status: str
    current_step: Optional[str] = None
    message: Optional[str] = None


class AudioResponse(BaseModel):
    """Response containing audio to play."""
    call_id: str
    audio_data: str  # Base64 encoded audio
    audio_format: str = "wav"
    text: Optional[str] = None
    next_step: Optional[str] = None
    is_complete: bool = False
    
    @classmethod
    def from_audio_bytes(
        cls,
        call_id: str,
        audio_data: bytes,
        audio_format: str = "wav",
        text: Optional[str] = None,
        next_step: Optional[str] = None,
        is_complete: bool = False
    ):
        """Create AudioResponse from bytes."""
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        return cls(
            call_id=call_id,
            audio_data=audio_base64,
            audio_format=audio_format,
            text=text,
            next_step=next_step,
            is_complete=is_complete
        )


class FeedbackResponse(BaseModel):
    """Feedback response summary."""
    call_id: str
    agreement_no: Optional[str] = None
    customer_name: Optional[str] = None
    is_compliant: Optional[bool] = None
    compliance_notes: Optional[str] = None
    responses: Dict[str, Any] = Field(default_factory=dict)
    completed_at: Optional[datetime] = None


class TextMessageResponse(BaseModel):
    """Response for text-to-text conversation."""
    call_id: str
    text: str = Field(..., description="Bot's text response")
    next_step: Optional[str] = None
    is_complete: bool = False

