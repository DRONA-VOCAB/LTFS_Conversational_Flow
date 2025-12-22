"""Outbound call service for initiating calls."""
from typing import Optional
from app.services.feedback_flow_manager import FeedbackFlowManager
from sqlalchemy.ext.asyncio import AsyncSession


class OutboundCallService:
    """Service for managing outbound calls."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def initiate_call(self, agreement_no: str) -> tuple[str, bytes]:
        """
        Initiate an outbound call for feedback survey.
        
        Args:
            agreement_no: Customer agreement number
        
        Returns:
            Tuple of (call_id, opening_audio)
        """
        flow_manager = FeedbackFlowManager(self.db)
        try:
            call_id, audio_data = await flow_manager.initialize_call(agreement_no)
            return call_id, audio_data
        finally:
            await flow_manager.close()
    
    async def process_call_audio(
        self,
        call_id: str,
        audio_data: bytes
    ) -> tuple[bytes, str, bool]:
        """
        Process audio chunk from call and return response.
        
        Args:
            call_id: Call identifier
            audio_data: Audio chunk from client
        
        Returns:
            Tuple of (response_audio, next_step, is_complete)
        """
        flow_manager = FeedbackFlowManager(self.db)
        try:
            return await flow_manager.process_audio_response(call_id, audio_data)
        finally:
            await flow_manager.close()

