"""Feedback response model."""
from sqlalchemy import Column, String, Integer, Numeric, DateTime, Boolean, Date, Text, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class FeedbackResponse(Base):
    """Feedback response table."""
    __tablename__ = "feedback_responses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    call_event_id = Column(Integer, ForeignKey("call_events.id"), nullable=False, index=True)
    agreement_no = Column(String(255), nullable=True, index=True)
    
    # Survey responses
    took_loan = Column(Boolean, nullable=True)
    made_payment_last_month = Column(Boolean, nullable=True)
    payment_made_by = Column(String(100), nullable=True)  # self, family, friend, third_party
    payee_name = Column(String(255), nullable=True)
    payee_contact = Column(String(50), nullable=True)
    last_payment_date = Column(Date, nullable=True)
    payment_mode = Column(String(100), nullable=True)
    field_executive_name = Column(String(255), nullable=True)
    field_executive_contact = Column(String(50), nullable=True)
    payment_reason = Column(String(100), nullable=True)  # EMI, EMI+Charges, Settlement, etc.
    actual_amount_paid = Column(Numeric(15, 2), nullable=True)
    
    # Compliance flags
    is_compliant = Column(Boolean, nullable=True)
    compliance_notes = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

