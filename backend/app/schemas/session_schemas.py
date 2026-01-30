"""Session-related schema definitions (legacy - not actively used)"""
from pydantic import BaseModel
from typing import Optional, List


class CreateSessionRequest(BaseModel):
    """Request schema for creating a new session"""
    customer_name: str


class CreateSessionResponse(BaseModel):
    """Response schema for session creation"""
    session_id: str
    customer_name: str
    question: Optional[str] = None
    status: str


class SubmitAnswerRequest(BaseModel):
    """Request schema for submitting an answer"""
    answer: str


class SubmitAnswerResponse(BaseModel):
    """Response schema for answer submission"""
    question: Optional[str] = None
    status: str  # "NEXT", "COMPLETED", "REPEAT", "END"
    message: Optional[str] = None
    skip_summary: bool = False  # True if should skip summary and go directly to closing


class SummaryResponse(BaseModel):
    """Response schema for session summary"""
    summary: str
    session_id: str


class ConfirmRequest(BaseModel):
    """Request schema for confirming summary"""
    confirmed: bool


class ConfirmResponse(BaseModel):
    """Response schema for confirmation"""
    closing_statement: str
    session_id: str



