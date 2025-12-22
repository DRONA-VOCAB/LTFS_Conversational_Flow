"""Call event model for tracking call state."""
from sqlalchemy import Column, String, Integer, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
from app.database import Base
import enum


class CallStatus(str, enum.Enum):
    """Call status enumeration."""
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


class CallEvent(Base):
    """Call event tracking table."""
    __tablename__ = "call_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(String(255), unique=True, nullable=False, index=True)
    customer_name = Column(String(255), nullable=True)
    agreement_no = Column(String(255), nullable=True, index=True)
    contact_number = Column(String(50), nullable=True)
    status = Column(SQLEnum(CallStatus), default=CallStatus.INITIATED)
    current_step = Column(String(100), nullable=True)
    conversation_state = Column(JSON, nullable=True)  # Store conversation state
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

