"""Session-related API routes"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import uuid
from datetime import datetime

from schemas.session_schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    SummaryResponse,
    ConfirmRequest,
    ConfirmResponse,
    CustomersListResponse,
)
from config.database import get_all_customers
from sessions.session_schema import create_session
from sessions.session_store import save_session, get_session
from flow.flow_manager import get_question_text, process_answer
from services.summary_service import (
    generate_human_summary,
    get_closing_statement,
    is_survey_completed,
    transliterate_to_devanagari,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/customers", response_model=CustomersListResponse)
async def get_customers():
    """Get list of all customers from database"""
    try:
        customers = get_all_customers()
        return CustomersListResponse(customers=customers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching customers: {str(e)}")


from config.database import get_all_customers, get_customer_by_name
from utils.session_data_storage import save_db_data, save_session_data

@router.post("", response_model=CreateSessionResponse)
async def create_session_endpoint(request: CreateSessionRequest):
    """Create a new survey session"""
    try:
        # Generate unique session ID
        session_id = f"session_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"

        # Create session with transliterated customer name
        customer_name_english = request.customer_name.strip() or "Customer"
        customer_name_hindi = transliterate_to_devanagari(customer_name_english)
        
        # Fetch ALL customer data from database (ONLY the selected customer)
        customer_data = get_customer_by_name(customer_name_english)
        
        # Save DB data to file
        if customer_data:
            save_db_data(session_id, customer_data)
        
        # Use Hindi name for TTS, store both
        session = create_session(session_id, customer_name_hindi)
        session["customer_name_english"] = customer_name_english  # Store original

        if customer_data and customer_data.get("product"):
            product = customer_data.get("product", "").upper()
            if product == "PL":
                session["product_type"] = "पर्सनल लोन"
            else:
                session["product_type"] = "पर्सनल लोन"
                # session["product_type"] = "टू-व्हीलर लोन" update when added two wheeler flow
        else:
            # Default to two wheeler if not found
            session["product_type"] = "टपर्सनल लोन"
            
        save_session(session)

        # Get first question
        question_text = get_question_text(session)
        save_session(session)

        return CreateSessionResponse(
            session_id=session_id,
            customer_name=customer_name_english,  # Return English for frontend display
            question=question_text,
            status="ACTIVE",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating session: {str(e)}")


@router.post("/{session_id}/answer", response_model=SubmitAnswerResponse)
async def submit_answer(session_id: str, request: SubmitAnswerRequest):
    """Submit an answer to the current question"""
    try:
        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if not request.answer.strip():
            return SubmitAnswerResponse(
                question=None, status="REPEAT", message="Please provide an answer."
            )

        # Process answer
        result = process_answer(session, request.answer.strip())
        save_session(session)

        if result in ["END", "CLOSING"]:
            save_session_data(session_id, session)

        if result == "END":
            return SubmitAnswerResponse(
                question=None,
                status="END",
                message="Maximum retries exceeded. Session ended.",
            )
        elif result == "REPEAT":
            # Get the same question again
            question_text = get_question_text(session)
            save_session(session)
            return SubmitAnswerResponse(
                question=question_text,
                status="REPEAT",
                message="Please provide a clearer answer.",
            )
        elif result == "COMPLETED":
            # Check if it's a wrong number case (loan_taken is NO) - skip summary
            skip_summary = session.get("loan_taken") == "NO" and session.get("call_should_end", False)
            return SubmitAnswerResponse(
                question=None,
                status="COMPLETED",
                message="Survey completed successfully.",
                skip_summary=skip_summary,
            )
        elif result == "NEXT":
            # Get next question
            question_text = get_question_text(session)
            save_session(session)
            return SubmitAnswerResponse(
                question=question_text, status="NEXT", message=None
            )
        else:
            raise HTTPException(status_code=500, detail=f"Unexpected result: {result}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing answer: {str(e)}"
        )


@router.get("/{session_id}/summary", response_model=SummaryResponse)
async def get_summary(session_id: str):
    """Get human-readable summary of the session"""
    try:
        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Check if survey is completed
        if not is_survey_completed(session):
            raise HTTPException(
                status_code=400,
                detail="Survey is not yet completed. Please complete all questions first.",
            )

        # Generate human-readable summary
        summary = generate_human_summary(session)

        return SummaryResponse(summary=summary, session_id=session_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating summary: {str(e)}"
        )


@router.post("/{session_id}/confirm", response_model=ConfirmResponse)
async def confirm_summary(session_id: str, request: ConfirmRequest):
    """Confirm the summary and get closing statement"""
    try:
        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if not request.confirmed:
            raise HTTPException(
                status_code=400,
                detail="Summary not confirmed. Please confirm to proceed.",
            )

        # Generate closing statement
        closing_statement = get_closing_statement(session)
        
        # Save session data to file when session completes
        save_session_data(session_id, session)

        return ConfirmResponse(
            closing_statement=closing_statement, session_id=session_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing confirmation: {str(e)}"
        )


@router.get("/{session_id}")
async def get_session_info(session_id: str) -> Dict[str, Any]:
    """Get session information"""
    try:
        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Return session data (excluding internal fields)
        session_info = {
            k: v
            for k, v in session.items()
            if k not in ["current_question", "retry_count"]
        }

        return session_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving session: {str(e)}"
        )
