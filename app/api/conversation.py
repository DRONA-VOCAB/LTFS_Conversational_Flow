"""Conversation API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
import time
from app.database import get_db
from app.services.outbound_call_service import OutboundCallService
from app.services.conversation_recorder import ConversationRecorder
from app.schema.feedback_request import CallInitiateRequest, TextMessageRequest
from app.schema.feedback_response import (
    CallStatusResponse,
    AudioResponse,
    FeedbackResponse as FeedbackResponseSchema,
    TextMessageResponse,
)
from app.models.call_event import CallEvent, CallStatus
from app.models.feedback_responses import FeedbackResponse as FeedbackResponseModel
from app.utils.exceptions import TTSServiceError
from sqlalchemy import select, func
from typing import Optional
import io

router = APIRouter(prefix="/api/v1", tags=["conversation"])

# Global conversation recorder instance
conversation_recorder = ConversationRecorder(recordings_dir="recordings")


@router.post("/call/initiate", response_model=AudioResponse)
async def initiate_call(
    request: CallInitiateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate a new feedback survey call.
    
    Returns the opening audio message.
    """
    try:
        call_service = OutboundCallService(db)
        call_id, audio_data = await call_service.initiate_call(request.agreement_no)
        
        # Start recording for this call
        conversation_recorder.start_recording(call_id)
        # Record opening bot message
        conversation_recorder.record_bot_audio(call_id, audio_data)
        
        return AudioResponse.from_audio_bytes(
            call_id=call_id,
            audio_data=audio_data,
            audio_format="wav",
            text="Call opening message",
            next_step="customer_verification",
            is_complete=False
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TTSServiceError as e:
        # TTS service is unavailable - provide helpful error with alternative
        raise HTTPException(
            status_code=503,  # Service Unavailable
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate call: {str(e)}")


@router.post("/call/{call_id}/audio", response_model=AudioResponse)
async def process_audio(
    call_id: str,
    audio_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Process audio chunk from client and return bot's audio response.
    
    This endpoint handles streaming voice-to-voice conversation.
    """
    request_start_time = time.perf_counter()
    try:
        # Read audio data
        read_start = time.perf_counter()
        audio_data = await audio_file.read()
        read_latency = time.perf_counter() - read_start
        
        if not audio_data:
            raise HTTPException(status_code=400, detail="No audio data provided")
        
        # Record user audio
        conversation_recorder.record_user_audio(call_id, audio_data)
        
        # Process audio
        process_start = time.perf_counter()
        call_service = OutboundCallService(db)
        response_audio, next_step, is_complete = await call_service.process_call_audio(
            call_id,
            audio_data
        )
        process_latency = time.perf_counter() - process_start
        
        if not response_audio:
            raise HTTPException(status_code=500, detail="Failed to generate response audio")
        
        # Record bot audio response
        conversation_recorder.record_bot_audio(call_id, response_audio)
        
        # If call is complete, finalize recording
        if is_complete:
            await conversation_recorder.finalize_recording(call_id)
        
        # Prepare response
        response_start = time.perf_counter()
        result = AudioResponse.from_audio_bytes(
            call_id=call_id,
            audio_data=response_audio,
            audio_format="wav",
            next_step=next_step,
            is_complete=is_complete
        )
        response_latency = time.perf_counter() - response_start
        
        # Calculate total latency
        total_latency = time.perf_counter() - request_start_time
        print(f"[API] Total request-response latency: {total_latency:.3f}s (read: {read_latency:.3f}s, process: {process_latency:.3f}s, response: {response_latency:.3f}s)")
        
        return result
    except ValueError as e:
        total_latency = time.perf_counter() - request_start_time
        print(f"[API] Request failed after {total_latency:.3f}s: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        total_latency = time.perf_counter() - request_start_time
        print(f"[API] Request failed after {total_latency:.3f}s: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process audio: {str(e)}")


@router.get("/call/{call_id}/status", response_model=CallStatusResponse)
async def get_call_status(
    call_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get current status of a call."""
    stmt = select(CallEvent).where(CallEvent.call_id == call_id)
    result = await db.execute(stmt)
    call_event = result.scalar_one_or_none()
    
    if not call_event:
        raise HTTPException(status_code=404, detail="Call not found")
    
    return CallStatusResponse(
        call_id=call_id,
        status=call_event.status.value,
        current_step=call_event.current_step,
        message=f"Call is {call_event.status.value}"
    )


@router.post("/call/{call_id}/audio/stream")
async def process_audio_stream(
    call_id: str,
    audio_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Process audio chunk and return audio response as binary stream.
    Alternative endpoint for direct audio streaming (no JSON wrapper).
    """
    try:
        audio_data = await audio_file.read()
        
        if not audio_data:
            raise HTTPException(status_code=400, detail="No audio data provided")
        
        # Record user audio
        conversation_recorder.record_user_audio(call_id, audio_data)
        
        call_service = OutboundCallService(db)
        response_audio, next_step, is_complete = await call_service.process_call_audio(
            call_id,
            audio_data
        )
        
        if not response_audio:
            raise HTTPException(status_code=500, detail="Failed to generate response audio")
        
        # Record bot audio response
        conversation_recorder.record_bot_audio(call_id, response_audio)
        
        # If call is complete, finalize recording
        if is_complete:
            await conversation_recorder.finalize_recording(call_id)
        
        # Return audio as binary stream
        return Response(
            content=response_audio,
            media_type="audio/wav",
            headers={
                "X-Call-ID": call_id,
                "X-Next-Step": next_step,
                "X-Is-Complete": str(is_complete).lower()
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process audio: {str(e)}")


@router.get("/call/{call_id}/feedback", response_model=FeedbackResponseSchema)
async def get_call_feedback(
    call_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get feedback response for a completed call."""
    # Get call event
    stmt = select(CallEvent).where(CallEvent.call_id == call_id)
    result = await db.execute(stmt)
    call_event = result.scalar_one_or_none()
    
    if not call_event:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Get feedback response
    stmt = select(FeedbackResponseModel).where(
        FeedbackResponseModel.call_event_id == call_event.id
    )
    result = await db.execute(stmt)
    feedback = result.scalar_one_or_none()
    
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found for this call")
    
    return FeedbackResponseSchema(
        call_id=call_id,
        agreement_no=feedback.agreement_no,
        customer_name=call_event.customer_name,
        is_compliant=feedback.is_compliant,
        compliance_notes=feedback.compliance_notes,
        responses={
            "took_loan": feedback.took_loan,
            "made_payment_last_month": feedback.made_payment_last_month,
            "payment_made_by": feedback.payment_made_by,
            "payee_name": feedback.payee_name,
            "payee_contact": feedback.payee_contact,
            "last_payment_date": str(feedback.last_payment_date) if feedback.last_payment_date else None,
            "payment_mode": feedback.payment_mode,
            "field_executive_name": feedback.field_executive_name,
            "field_executive_contact": feedback.field_executive_contact,
            "payment_reason": feedback.payment_reason,
            "actual_amount_paid": float(feedback.actual_amount_paid) if feedback.actual_amount_paid else None,
        },
        completed_at=call_event.completed_at
    )


@router.post("/conversation/text/initiate", response_model=TextMessageResponse)
async def initiate_text_conversation(
    request: CallInitiateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate a new text-to-text feedback survey conversation.
    
    This endpoint does NOT use TTS or ASR services - it works purely with text.
    Returns the opening text message.
    
    Use this endpoint to avoid TTS/ASR service dependencies and connection issues.
    """
    try:
        from app.services.feedback_flow_manager import FeedbackFlowManager
        
        flow_manager = FeedbackFlowManager(db)
        call_id, opening_text = await flow_manager.initialize_text_conversation(request.agreement_no)
        
        return TextMessageResponse(
            call_id=call_id,
            text=opening_text,
            next_step="customer_verification",
            is_complete=False
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate conversation: {str(e)}")


@router.post("/conversation/text/message", response_model=TextMessageResponse)
async def process_text_message(
    request: TextMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Process a text message and return bot's text response.
    
    This endpoint handles text-to-text conversation flow.
    Does NOT use TTS or ASR services - works purely with text input/output.
    
    Use this endpoint to avoid TTS/ASR service dependencies and connection issues.
    """
    try:
        from app.services.feedback_flow_manager import FeedbackFlowManager
        
        flow_manager = FeedbackFlowManager(db)
        response_text, next_step, is_complete = await flow_manager.process_text_response(
            request.call_id,
            request.text
        )
        
        return TextMessageResponse(
            call_id=request.call_id,
            text=response_text,
            next_step=next_step,
            is_complete=is_complete
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")


@router.get("/customers")
async def list_customers(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List available customers with agreement numbers for testing."""
    from app.database import CustomerData
    
    stmt = select(CustomerData).offset(offset).limit(limit)
    result = await db.execute(stmt)
    customers = result.scalars().all()
    
    customer_list = []
    for customer in customers:
        customer_list.append({
            "agreement_no": customer.agreement_no,
            "customer_name": customer.customer_name,
            "contact_number": customer.contact_number,
            "has_payment": customer.payment_amt is not None and customer.payment_amt > 0,
            "payment_amount": float(customer.payment_amt) if customer.payment_amt else None,
            "deposition_date": str(customer.deposition_date) if customer.deposition_date else None,
        })
    
    total_stmt = select(func.count(CustomerData.id))
    total_result = await db.execute(total_stmt)
    total = total_result.scalar()
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "customers": customer_list
    }


@router.get("/call/{call_id}/recording")
async def get_call_recording(call_id: str):
    """
    Download the recording for a completed call.
    
    Returns the combined recording file (user + bot audio interleaved).
    """
    recording_path = conversation_recorder.get_recording_path(call_id)
    
    if not recording_path:
        raise HTTPException(
            status_code=404,
            detail=f"Recording not found for call: {call_id}"
        )
    
    return FileResponse(
        path=recording_path,
        media_type="audio/wav",
        filename=f"{call_id}_recording.wav"
    )


@router.get("/call/{call_id}/recording/user")
async def get_user_recording(call_id: str):
    """Download the user-only recording for a call."""
    from pathlib import Path
    recordings_dir = Path("recordings")
    pattern = f"{call_id}_user_*.wav"
    matching_files = list(recordings_dir.glob(pattern))
    
    if not matching_files:
        raise HTTPException(
            status_code=404,
            detail=f"User recording not found for call: {call_id}"
        )
    
    # Return the most recent one
    file_path = max(matching_files, key=lambda p: p.stat().st_mtime)
    return FileResponse(
        path=str(file_path),
        media_type="audio/wav",
        filename=f"{call_id}_user_recording.wav"
    )


@router.get("/call/{call_id}/recording/bot")
async def get_bot_recording(call_id: str):
    """Download the bot-only recording for a call."""
    from pathlib import Path
    recordings_dir = Path("recordings")
    pattern = f"{call_id}_bot_*.wav"
    matching_files = list(recordings_dir.glob(pattern))
    
    if not matching_files:
        raise HTTPException(
            status_code=404,
            detail=f"Bot recording not found for call: {call_id}"
        )
    
    # Return the most recent one
    file_path = max(matching_files, key=lambda p: p.stat().st_mtime)
    return FileResponse(
        path=str(file_path),
        media_type="audio/wav",
        filename=f"{call_id}_bot_recording.wav"
    )

