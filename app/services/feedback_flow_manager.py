"""Feedback flow manager - handles the conversation flow logic."""
from typing import Optional, Dict, Any, Tuple
import time
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.asr_service import ASRService
from app.services.tts_service import TTSService
from app.services.llm_service import LLMService
from app.services.intent_service import IntentService, EmotionType
from app.models.call_event import CallEvent, CallStatus
from app.models.feedback_responses import FeedbackResponse as FeedbackResponseModel
from app.database import CustomerData
from app.utils.validators import (
    validate_yes_no_response,
    validate_payment_mode,
    validate_payment_reason,
    validate_payment_made_by,
    extract_date_from_text,
    extract_amount_from_text,
    check_payment_compliance,
    check_date_compliance,
    check_amount_compliance,
    check_payment_mode_compliance,
)
from app.utils.formatter import format_customer_name, get_greeting
from app.utils.exceptions import TTSServiceError


class ConversationStep:
    """Conversation step constants."""
    CALL_OPENING = "call_opening"
    CUSTOMER_VERIFICATION = "customer_verification"
    PURPOSE_EXPLANATION_PART1 = "purpose_explanation_part1"  
    PURPOSE_EXPLANATION_PART2 = "purpose_explanation_part2"  
    LOAN_CONFIRMATION = "loan_confirmation"
    PAYMENT_CONFIRMATION = "payment_confirmation"
    PAYMENT_MADE_BY = "payment_made_by"
    PAYEE_DETAILS = "payee_details"
    PAYMENT_DATE = "payment_date"
    PAYMENT_MODE = "payment_mode"
    FIELD_EXECUTIVE_DETAILS = "field_executive_details"
    PAYMENT_REASON = "payment_reason"
    VEHICLE_USER = "vehicle_user"          # TW-only question: who is using the vehicle
    VEHICLE_STATUS = "vehicle_status"      # TW-only question: status of the vehicle
    PAYMENT_AMOUNT = "payment_amount"
    CALL_CLOSING = "call_closing"
    CALL_ENDED = "call_ended"


class FeedbackFlowManager:
    """Manages the feedback survey conversation flow."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.asr_service = ASRService()
        self.tts_service = TTSService()
        self.llm_service = LLMService()
        self.intent_service = IntentService(self.llm_service)
        self.call_event: Optional[CallEvent] = None
        self.customer_data: Optional[CustomerData] = None
        self.responses: Dict[str, Any] = {}
        self.compliance_notes: list = []
        
        self.expected_outcomes = {
            ConversationStep.CALL_OPENING: ["yes", "no"],
            ConversationStep.CUSTOMER_VERIFICATION: ["yes", "no", "alternate_contact", "schedule_time"],
            ConversationStep.PURPOSE_EXPLANATION_PART1: ["acknowledge", "proceed"],
            ConversationStep.LOAN_CONFIRMATION: ["yes", "no"],
            ConversationStep.PAYMENT_CONFIRMATION: ["yes", "no"],
            ConversationStep.PAYMENT_MADE_BY: ["self", "family", "friend", "third_party"],
            ConversationStep.PAYEE_DETAILS: ["name", "contact", "both"],
            ConversationStep.PAYMENT_DATE: ["date"],
            ConversationStep.PAYMENT_MODE: [
                "online", "upi", "neft", "rtgs", "cash", 
                "branch", "outlet", "nach", "field_executive"
            ],
            ConversationStep.FIELD_EXECUTIVE_DETAILS: ["name", "contact", "both"],
            ConversationStep.PAYMENT_REASON: [
                "emi", "emi+charges", "settlement", "foreclosure",
                "charges", "loan_cancellation", "advance_emi"
            ],
            # TW-only steps are treated as free-text; we don't enforce specific outcomes
            ConversationStep.VEHICLE_USER: [],
            ConversationStep.VEHICLE_STATUS: [],
            ConversationStep.PAYMENT_AMOUNT: ["amount"],
        }
    
    async def initialize_call(self, agreement_no: str) -> Tuple[str, bytes]:
        """
        Initialize a new call and return opening message.
        
        Returns:
            Tuple of (call_id, audio_data)
        """
        # Fetch customer data
        stmt = select(CustomerData).where(CustomerData.agreement_no == agreement_no)
        result = await self.db.execute(stmt)
        self.customer_data = result.scalar_one_or_none()
        
        if not self.customer_data:
            raise ValueError(f"Customer not found for agreement number: {agreement_no}")
        
        # Create call event
        call_id = f"call_{agreement_no}_{int(datetime.now().timestamp())}"
        self.call_event = CallEvent(
            call_id=call_id,
            customer_name=self.customer_data.customer_name,
            agreement_no=agreement_no,
            contact_number=self.customer_data.contact_number,
            status=CallStatus.IN_PROGRESS,
            current_step=ConversationStep.CALL_OPENING,
            conversation_state={
                "step": ConversationStep.CALL_OPENING,
                "customer_name": self.customer_data.customer_name,
                "agreement_no": agreement_no,
            }
        )
        self.db.add(self.call_event)
        await self.db.commit()
        await self.db.refresh(self.call_event)
        
        # Generate opening message
        greeting = get_greeting()
        # Detect gender from name for proper title (Ms/Mr)
        customer_name_formatted = format_customer_name(self.customer_data.customer_name)
        opening_text = f"{greeting}. I am calling on behalf of L&T Finance. Am I speaking with {customer_name_formatted}?"
        
        start_time = time.perf_counter()
        try:
            audio_data, tts_latency = await self.tts_service.synthesize_with_retry(opening_text)
            if not audio_data:
                raise TTSServiceError(
                    "Failed to generate TTS audio - service is unreachable or returned no data",
                    service_url=self.tts_service.tts_url
                )
            total_latency = time.perf_counter() - start_time
            print(f"[FlowManager] Call initialization latency: {total_latency:.3f}s (TTS: {tts_latency:.3f}s)")
            
            if len(audio_data) == 0:
                raise TTSServiceError(
                    "TTS service returned empty audio data",
                    service_url=self.tts_service.tts_url
                )
            
            print(f"[FlowManager] Generated opening audio: {len(audio_data)} bytes")
        except TTSServiceError:
            # Re-raise TTS errors as-is
            raise
        except Exception as e:
            # Log error with timing info if available
            try:
                elapsed = time.perf_counter() - start_time
                print(f"[FlowManager] Error during call initialization after {elapsed:.3f}s: {str(e)}")
            except:
                print(f"[FlowManager] Error during call initialization: {str(e)}")
            # Wrap unexpected errors as TTS errors
            raise TTSServiceError(
                f"Unexpected error during TTS generation: {str(e)}",
                service_url=self.tts_service.tts_url
            ) from e
        
        return call_id, audio_data
    
    async def initialize_text_conversation(self, agreement_no: str) -> Tuple[str, str]:
        """
        Initialize a new text conversation and return opening message.
        
        Returns:
            Tuple of (call_id, opening_text)
        """
        # Fetch customer data
        stmt = select(CustomerData).where(CustomerData.agreement_no == agreement_no)
        result = await self.db.execute(stmt)
        self.customer_data = result.scalar_one_or_none()
        
        if not self.customer_data:
            raise ValueError(f"Customer not found for agreement number: {agreement_no}")
        
        # Create call event
        call_id = f"call_{agreement_no}_{int(datetime.now().timestamp())}"
        self.call_event = CallEvent(
            call_id=call_id,
            customer_name=self.customer_data.customer_name,
            agreement_no=agreement_no,
            contact_number=self.customer_data.contact_number,
            status=CallStatus.IN_PROGRESS,
            current_step=ConversationStep.CALL_OPENING,
            conversation_state={
                "step": ConversationStep.CALL_OPENING,
                "customer_name": self.customer_data.customer_name,
                "agreement_no": agreement_no,
            }
        )
        self.db.add(self.call_event)
        await self.db.commit()
        await self.db.refresh(self.call_event)
        
        # Generate opening message
        greeting = get_greeting()
        customer_name_formatted = format_customer_name(self.customer_data.customer_name)
        opening_text = f"{greeting}. I am calling on behalf of L&T Finance. Am I speaking with {customer_name_formatted}?"
        
        print(f"[FlowManager] Initialized text conversation: {call_id}")
        return call_id, opening_text
    
    async def process_text_response(
        self,
        call_id: str,
        text: str
    ) -> Tuple[str, str, bool]:
        """
        Process text response and return next text, next step, and completion status.
        
        Returns:
            Tuple of (response_text, next_step, is_complete)
        """
        overall_start_time = time.perf_counter()
        # Load call event
        if not self.call_event or self.call_event.call_id != call_id:
            stmt = select(CallEvent).where(CallEvent.call_id == call_id)
            result = await self.db.execute(stmt)
            self.call_event = result.scalar_one_or_none()
            
            if not self.call_event:
                raise ValueError(f"Call event not found: {call_id}")
            
            # Load customer data
            if self.call_event.agreement_no:
                stmt = select(CustomerData).where(
                    CustomerData.agreement_no == self.call_event.agreement_no
                )
                result = await self.db.execute(stmt)
                self.customer_data = result.scalar_one_or_none()
        
        text = text.strip()
        if not text:
            response_text = "I'm sorry, I didn't receive your message. Could you please repeat?"
            overall_latency = time.perf_counter() - overall_start_time
            print(f"[FlowManager] Text processing latency: {overall_latency:.3f}s")
            return response_text, self.call_event.current_step, False
        
        current_step = self.call_event.current_step
        
        # Special handling for PAYMENT_DATE - check for date BEFORE intent checking
        if current_step == ConversationStep.PAYMENT_DATE:
            payment_date = extract_date_from_text(text)
            if payment_date:
                print(f"[FlowManager] Date found in text '{text}': {payment_date}, proceeding directly to date handler (skipping intent check)")
                return await self._handle_payment_date_text(text, None)
        
        # Special handling for PAYMENT_AMOUNT - check for amount BEFORE intent checking
        if current_step == ConversationStep.PAYMENT_AMOUNT:
            amount = extract_amount_from_text(text)
            if amount:
                print(f"[FlowManager] Amount found in text '{text}': {amount}, proceeding directly to amount handler (skipping intent check)")
                return await self._handle_payment_amount_text(text, None)
        
        if current_step == ConversationStep.PURPOSE_EXPLANATION_PART1:
            print(f"[FlowManager] PURPOSE_EXPLANATION_PART1 step detected, proceeding directly to loan confirmation")
            self.call_event.current_step = ConversationStep.LOAN_CONFIRMATION
            response_text = "Did you take the loan from L&T Finance?"
            await self._update_call_event()
            overall_latency = time.perf_counter() - overall_start_time
            print(f"[FlowManager] Text processing latency: {overall_latency:.3f}s")
            return response_text, self.call_event.current_step, False
        
        # Extract intent and emotion
        expected_outcomes = self.expected_outcomes.get(current_step, [])
        context = {
            "current_step": current_step,
            "responses": self.responses,
            "customer_name": self.customer_data.customer_name if self.customer_data else None,
        }
        
        intent_result = await self.intent_service.extract_intent_and_emotion(
            text=text,
            current_step=current_step,
            expected_outcomes=expected_outcomes,
            context=context
        )
        
        # Log intent extraction result
        if intent_result and intent_result.is_expected:
            print(f"[FlowManager] Step: {current_step}, Text: '{text[:50]}...', Intent: {intent_result.intent}, Extracted: {intent_result.extracted_value}, Status: SUCCESS")
            # Reset retry counter on successful intent extraction
            retry_key = f"{current_step}_retry_count"
            if retry_key in self.responses:
                self.responses[retry_key] = 0
        else:
            print(f"[FlowManager] Step: {current_step}, Text: '{text[:50]}...', Intent: {intent_result.intent if intent_result else 'None'}, Status: NEEDS_EMPATHETIC_RESPONSE")
        
        # Check retry limit to prevent infinite loops (text flow)
        retry_key = f"{current_step}_retry_count"
        if retry_key not in self.responses:
            self.responses[retry_key] = 0
        
        # Only increment retry counter if intent extraction failed
        if intent_result and intent_result.needs_llm_response:
            self.responses[retry_key] += 1
        
        max_retries = 3  # Maximum retries before skipping/ending
        
        if intent_result.needs_llm_response:
            # If we've exceeded max retries, skip this question or end call gracefully
            if self.responses[retry_key] > max_retries:
                print(f"[FlowManager] Max retries ({max_retries}) exceeded for step {current_step}, skipping to next step or ending call")
                # Try to skip to next step based on current step
                if current_step == ConversationStep.CALL_OPENING:
                    return await self._handle_call_closing_text()
                elif current_step == ConversationStep.LOAN_CONFIRMATION:
                    return await self._handle_call_closing_text()
                elif current_step == ConversationStep.PAYMENT_CONFIRMATION:
                    return await self._handle_call_closing_text()
                elif current_step == ConversationStep.PAYMENT_MADE_BY:
                    self.responses["payment_made_by"] = "self"
                    self.call_event.current_step = ConversationStep.PAYMENT_DATE
                    response_text = "When did you make your last payment?"
                    await self._update_call_event()
                    return response_text, self.call_event.current_step, False
                elif current_step == ConversationStep.PAYMENT_DATE:
                    self.call_event.current_step = ConversationStep.PAYMENT_MODE
                    response_text = "By which mode was the payment made? Options are: Online, UPI, NEFT, RTGS in LAN, Online or UPI to Field Executive, Cash, Branch, Outlet, or NACH which is auto debit from account."
                    await self._update_call_event()
                    return response_text, self.call_event.current_step, False
                elif current_step == ConversationStep.PAYMENT_MODE:
                    self.responses["payment_mode"] = "online"
                    self.call_event.current_step = ConversationStep.PAYMENT_REASON
                    response_text = "What was the reason for the payment? Was it for EMI, EMI plus charges, Settlement, Foreclosure, Charges, Loan cancellation, or Advance EMI?"
                    await self._update_call_event()
                    return response_text, self.call_event.current_step, False
                elif current_step == ConversationStep.PAYMENT_REASON:
                    self.responses["payment_reason"] = "emi"
                    product = (self.customer_data.product or "").strip().upper() if self.customer_data else ""
                    if product.startswith("TW") or "TWO WHEELER" in product:
                        self.call_event.current_step = ConversationStep.VEHICLE_USER
                        response_text = "Who is currently using the vehicle?"
                    else:
                        self.call_event.current_step = ConversationStep.PAYMENT_AMOUNT
                        response_text = "What was the actual amount paid?"
                    await self._update_call_event()
                    return response_text, self.call_event.current_step, False
                elif current_step in [ConversationStep.VEHICLE_USER, ConversationStep.VEHICLE_STATUS]:
                    if current_step == ConversationStep.VEHICLE_USER:
                        self.responses["vehicle_user"] = "Not provided"
                    else:
                        self.responses["vehicle_status"] = "Not provided"
                    self.call_event.current_step = ConversationStep.PAYMENT_AMOUNT
                    response_text = "What was the actual amount paid?"
                    await self._update_call_event()
                    return response_text, self.call_event.current_step, False
                elif current_step == ConversationStep.PAYMENT_AMOUNT:
                    return await self._handle_call_closing_text()
                else:
                    return await self._handle_call_closing_text()
            # Special handling for CALL_OPENING - try harder to detect yes/no
            if current_step == ConversationStep.CALL_OPENING:
                direct_yes_no = validate_yes_no_response(text)
                if direct_yes_no is not None:
                    print(f"[FlowManager] Found yes/no in empathetic path: {direct_yes_no}, proceeding to customer verification")
                    return await self._handle_customer_verification_text(text, intent_result)
            
            empathetic_text = await self.intent_service.generate_empathetic_response(
                user_text=text,
                emotion=intent_result.emotion,
                current_step=current_step,
                context=context
            )
            
            # Get the current question text to re-ask
            current_question = await self._get_current_question_text(current_step)
            
            if current_question:
                # Add a natural transition if the empathetic response doesn't already include the question
                if current_question.lower() not in empathetic_text.lower():
                    # Use natural connectors based on emotion
                    if intent_result.emotion in [EmotionType.FRUSTRATED, EmotionType.ANGRY]:
                        connector = "Let me make this quick. "
                    elif intent_result.emotion == EmotionType.CONFUSED:
                        connector = "Let me ask this differently. "
                    else:
                        connector = "So, "
                    combined_text = f"{empathetic_text} {connector}{current_question}"
                else:
                    combined_text = empathetic_text
            else:
                combined_text = empathetic_text
            
            overall_latency = time.perf_counter() - overall_start_time
            print(f"[FlowManager] Text processing latency: {overall_latency:.3f}s")
            return combined_text, current_step, False
        
        # Process based on current step with intent result
        if current_step == ConversationStep.CALL_OPENING:
            return await self._handle_customer_verification_text(text, intent_result)
        elif current_step == ConversationStep.CUSTOMER_VERIFICATION:
            # Check if we're waiting for alternate contact info
            if self.responses.get("waiting_for_alternate_contact"):
                return await self._handle_alternate_contact_text(text, intent_result)
            else:
                # Fallback: ask for alternate contact
                return await self._handle_alternate_contact_text(text, intent_result)
        elif current_step == ConversationStep.LOAN_CONFIRMATION:
            return await self._handle_loan_confirmation_text(text, intent_result)
        elif current_step == ConversationStep.PAYMENT_CONFIRMATION:
            return await self._handle_payment_confirmation_text(text, intent_result)
        elif current_step == ConversationStep.PAYMENT_MADE_BY:
            return await self._handle_payment_made_by_text(text, intent_result)
        elif current_step == ConversationStep.PAYEE_DETAILS:
            return await self._handle_payment_date_text(text, intent_result)
        elif current_step == ConversationStep.PAYMENT_DATE:
            return await self._handle_payment_date_text(text, intent_result)
        elif current_step == ConversationStep.PAYMENT_MODE:
            return await self._handle_payment_mode_text(text, intent_result)
        elif current_step == ConversationStep.FIELD_EXECUTIVE_DETAILS:
            return await self._handle_field_executive_details_text(text, intent_result)
        elif current_step == ConversationStep.PAYMENT_REASON:
            return await self._handle_payment_reason_text(text, intent_result)
        elif current_step == ConversationStep.VEHICLE_USER:
            return await self._handle_vehicle_user_text(text, intent_result)
        elif current_step == ConversationStep.VEHICLE_STATUS:
            return await self._handle_vehicle_status_text(text, intent_result)
        elif current_step == ConversationStep.PAYMENT_AMOUNT:
            return await self._handle_payment_amount_text(text, intent_result)
        else:
            return await self._handle_call_closing_text()
    
    async def process_audio_response(
        self,
        call_id: str,
        audio_data: bytes
    ) -> Tuple[bytes, str, bool]:
        """
        Process audio response and return next audio, next step, and completion status.
        
        Returns:
            Tuple of (audio_data, next_step, is_complete)
        """
        overall_start_time = time.perf_counter()
        # Load call event
        if not self.call_event or self.call_event.call_id != call_id:
            stmt = select(CallEvent).where(CallEvent.call_id == call_id)
            result = await self.db.execute(stmt)
            self.call_event = result.scalar_one_or_none()
            
            if not self.call_event:
                raise ValueError(f"Call event not found: {call_id}")
            
            # Load customer data
            if self.call_event.agreement_no:
                stmt = select(CustomerData).where(
                    CustomerData.agreement_no == self.call_event.agreement_no
                )
                result = await self.db.execute(stmt)
                self.customer_data = result.scalar_one_or_none()
        
        # Transcribe audio
        asr_start = time.perf_counter()
        text = await self.asr_service.transcribe(audio_data)
        asr_latency = time.perf_counter() - asr_start
        print(f"[FlowManager] ASR transcription latency: {asr_latency:.3f}s")
        
        if not text:
            # If ASR fails, ask to repeat
            response_text = "I'm sorry, I couldn't hear you clearly. Could you please repeat?"
            response_audio, tts_latency = await self.tts_service.synthesize_with_retry(response_text)
            if not response_audio:
                raise Exception("Failed to synthesize audio for repeat request")
            overall_latency = time.perf_counter() - overall_start_time
            processing_time = overall_latency - asr_latency - tts_latency
            print(f"[FlowManager] Complete request-response latency: {overall_latency:.3f}s")
            print(f"[FlowManager]   - ASR (transcription): {asr_latency:.3f}s")
            print(f"[FlowManager]   - Processing: {processing_time:.3f}s")
            print(f"[FlowManager]   - TTS (synthesis): {tts_latency:.3f}s")
            return response_audio, self.call_event.current_step, False
        
        text = text.strip()
        current_step = self.call_event.current_step
        
        # Special handling for PAYMENT_DATE - check for date BEFORE intent checking
        if current_step == ConversationStep.PAYMENT_DATE:
            payment_date = extract_date_from_text(text)
            if payment_date:
                print(f"[FlowManager] Date found in audio '{text}': {payment_date}, proceeding directly to date handler (skipping intent check)")
                return await self._handle_payment_date(text, None)
        
        # Special handling for PAYMENT_AMOUNT - check for amount BEFORE intent checking
        if current_step == ConversationStep.PAYMENT_AMOUNT:
            amount = extract_amount_from_text(text)
            if amount:
                print(f"[FlowManager] Amount found in audio '{text}': {amount}, proceeding directly to amount handler (skipping intent check)")
                return await self._handle_payment_amount(text, None)
        
        if current_step == ConversationStep.PURPOSE_EXPLANATION_PART1:
            print(f"[FlowManager] PURPOSE_EXPLANATION_PART1 step detected, proceeding directly to loan confirmation")
            self.call_event.current_step = ConversationStep.LOAN_CONFIRMATION
            response_text = "Did you take the loan from L&T Finance?"
            response_audio, tts_latency = await self.tts_service.synthesize_with_retry(response_text)
            if not response_audio:
                raise Exception("Failed to synthesize audio for loan confirmation question")
            await self._update_call_event()
            overall_latency = time.perf_counter() - overall_start_time
            processing_time = overall_latency - asr_latency - tts_latency
            print(f"[FlowManager] Complete request-response latency: {overall_latency:.3f}s")
            print(f"[FlowManager]   - ASR (transcription): {asr_latency:.3f}s")
            print(f"[FlowManager]   - Processing: {processing_time:.3f}s")
            print(f"[FlowManager]   - TTS (synthesis): {tts_latency:.3f}s")
            return response_audio, self.call_event.current_step, False
        
        # Extract intent and emotion
        expected_outcomes = self.expected_outcomes.get(current_step, [])
        context = {
            "current_step": current_step,
            "responses": self.responses,
            "customer_name": self.customer_data.customer_name if self.customer_data else None,
        }
        
        intent_result = await self.intent_service.extract_intent_and_emotion(
            text=text,
            current_step=current_step,
            expected_outcomes=expected_outcomes,
            context=context
        )
        
        # Log intent extraction result
        if intent_result and intent_result.is_expected:
            print(f"[FlowManager] Step: {current_step}, Text: '{text[:50]}...', Intent: {intent_result.intent}, Extracted: {intent_result.extracted_value}, Status: SUCCESS (proceeding with normal flow)")
            # Reset retry counter on successful intent extraction
            retry_key = f"{current_step}_retry_count"
            if retry_key in self.responses:
                self.responses[retry_key] = 0
        else:
            print(f"[FlowManager] Step: {current_step}, Text: '{text[:50]}...', Intent: {intent_result.intent if intent_result else 'None'}, Status: NEEDS_EMPATHETIC_RESPONSE (generating empathetic response)")
        
        # Check retry limit to prevent infinite loops
        retry_key = f"{current_step}_retry_count"
        if retry_key not in self.responses:
            self.responses[retry_key] = 0
        
        # Only increment retry counter if intent extraction failed
        if intent_result and intent_result.needs_llm_response:
            self.responses[retry_key] += 1
        
        max_retries = 3  # Maximum retries before skipping/ending
        
        if intent_result.needs_llm_response:
            # If we've exceeded max retries, skip this question or end call gracefully
            if self.responses[retry_key] > max_retries:
                print(f"[FlowManager] Max retries ({max_retries}) exceeded for step {current_step}, skipping to next step or ending call")
                # Try to skip to next step based on current step
                if current_step == ConversationStep.CALL_OPENING:
                    # Can't skip opening, end call
                    return await self._handle_call_closing()
                elif current_step == ConversationStep.LOAN_CONFIRMATION:
                    # If can't confirm loan, end call
                    return await self._handle_call_closing()
                elif current_step == ConversationStep.PAYMENT_CONFIRMATION:
                    # If can't confirm payment, end call
                    return await self._handle_call_closing()
                elif current_step == ConversationStep.PAYMENT_MADE_BY:
                    # Skip to payment date (assume self)
                    self.responses["payment_made_by"] = "self"
                    self.call_event.current_step = ConversationStep.PAYMENT_DATE
                    response_text = "When did you make your last payment?"
                    response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
                    await self._update_call_event()
                    return response_audio, self.call_event.current_step, False
                elif current_step == ConversationStep.PAYMENT_DATE:
                    # Skip to payment mode
                    self.call_event.current_step = ConversationStep.PAYMENT_MODE
                    response_text = "By which mode was the payment made? Options are: Online, UPI, NEFT, RTGS in LAN, Online or UPI to Field Executive, Cash, Branch, Outlet, or NACH which is auto debit from account."
                    response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
                    await self._update_call_event()
                    return response_audio, self.call_event.current_step, False
                elif current_step == ConversationStep.PAYMENT_MODE:
                    # Skip to payment reason (assume online)
                    self.responses["payment_mode"] = "online"
                    self.call_event.current_step = ConversationStep.PAYMENT_REASON
                    response_text = "What was the reason for the payment? Was it for EMI, EMI plus charges, Settlement, Foreclosure, Charges, Loan cancellation, or Advance EMI?"
                    response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
                    await self._update_call_event()
                    return response_audio, self.call_event.current_step, False
                elif current_step == ConversationStep.PAYMENT_REASON:
                    # Skip to amount (assume EMI)
                    self.responses["payment_reason"] = "emi"
                    product = (self.customer_data.product or "").strip().upper() if self.customer_data else ""
                    if product.startswith("TW") or "TWO WHEELER" in product:
                        self.call_event.current_step = ConversationStep.VEHICLE_USER
                        response_text = "Who is currently using the vehicle?"
                    else:
                        self.call_event.current_step = ConversationStep.PAYMENT_AMOUNT
                        response_text = "What was the actual amount paid?"
                    response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
                    await self._update_call_event()
                    return response_audio, self.call_event.current_step, False
                elif current_step in [ConversationStep.VEHICLE_USER, ConversationStep.VEHICLE_STATUS]:
                    # Skip vehicle questions, go to amount
                    if current_step == ConversationStep.VEHICLE_USER:
                        self.responses["vehicle_user"] = "Not provided"
                    else:
                        self.responses["vehicle_status"] = "Not provided"
                    self.call_event.current_step = ConversationStep.PAYMENT_AMOUNT
                    response_text = "What was the actual amount paid?"
                    response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
                    await self._update_call_event()
                    return response_audio, self.call_event.current_step, False
                elif current_step == ConversationStep.PAYMENT_AMOUNT:
                    # Can't get amount, end call
                    return await self._handle_call_closing()
                else:
                    # Default: end call
                    return await self._handle_call_closing()
            # Special handling for CALL_OPENING - try harder to detect yes/no
            if current_step == ConversationStep.CALL_OPENING:
                direct_yes_no = validate_yes_no_response(text)
                if direct_yes_no is not None:
                    print(f"[FlowManager] Found yes/no in empathetic path: {direct_yes_no}, proceeding to customer verification")
                    return await self._handle_customer_verification(text, intent_result)
            
            empathetic_text = await self.intent_service.generate_empathetic_response(
                user_text=text,
                emotion=intent_result.emotion,
                current_step=current_step,
                context=context
            )
            
            # Get the current question text to re-ask
            current_question = await self._get_current_question_text(current_step)
            
            if current_question:
                # Add a natural transition if the empathetic response doesn't already include the question
                if current_question.lower() not in empathetic_text.lower():
                    # Use natural connectors based on emotion
                    if intent_result.emotion in [EmotionType.FRUSTRATED, EmotionType.ANGRY]:
                        connector = "Let me make this quick. "
                    elif intent_result.emotion == EmotionType.CONFUSED:
                        connector = "Let me ask this differently. "
                    else:
                        connector = "So, "
                    combined_text = f"{empathetic_text} {connector}{current_question}"
                else:
                    combined_text = empathetic_text
            else:
                combined_text = empathetic_text
            
            response_audio, tts_latency = await self.tts_service.synthesize_with_retry(combined_text)
            if not response_audio:
                # Fallback: try to re-ask the question without empathetic response
                current_question = await self._get_current_question_text(current_step)
                if current_question:
                    response_audio, tts_latency = await self.tts_service.synthesize_with_retry(current_question)
                if not response_audio:
                    raise Exception(f"Failed to synthesize audio for step {current_step}")
            overall_latency = time.perf_counter() - overall_start_time
            processing_time = overall_latency - asr_latency - tts_latency
            print(f"[FlowManager] Complete request-response latency: {overall_latency:.3f}s")
            print(f"[FlowManager]   - ASR (transcription): {asr_latency:.3f}s")
            print(f"[FlowManager]   - Processing (intent/flow): {processing_time:.3f}s")
            print(f"[FlowManager]   - TTS (synthesis): {tts_latency:.3f}s")
            return response_audio, current_step, False
        
        # Process based on current step with intent result
        if current_step == ConversationStep.CALL_OPENING:
            return await self._handle_customer_verification(text, intent_result)
        elif current_step == ConversationStep.CUSTOMER_VERIFICATION:
            # Check if we're waiting for alternate contact info
            if self.responses.get("waiting_for_alternate_contact"):
                return await self._handle_alternate_contact(text, intent_result)
        # PURPOSE_EXPLANATION_PART1 is handled above before intent checking
        elif current_step == ConversationStep.LOAN_CONFIRMATION:
            return await self._handle_loan_confirmation(text, intent_result)
        elif current_step == ConversationStep.PAYMENT_CONFIRMATION:
            return await self._handle_payment_confirmation(text, intent_result)
        elif current_step == ConversationStep.PAYMENT_MADE_BY:
            return await self._handle_payment_made_by(text, intent_result)
        elif current_step == ConversationStep.PAYEE_DETAILS:
            return await self._handle_payment_date(text, intent_result)
        elif current_step == ConversationStep.PAYMENT_DATE:
            return await self._handle_payment_date(text, intent_result)
        elif current_step == ConversationStep.PAYMENT_MODE:
            return await self._handle_payment_mode(text, intent_result)
        elif current_step == ConversationStep.FIELD_EXECUTIVE_DETAILS:
            return await self._handle_field_executive_details(text, intent_result)
        elif current_step == ConversationStep.PAYMENT_REASON:
            return await self._handle_payment_reason(text, intent_result)
        elif current_step == ConversationStep.VEHICLE_USER:
            return await self._handle_vehicle_user(text, intent_result)
        elif current_step == ConversationStep.VEHICLE_STATUS:
            return await self._handle_vehicle_status(text, intent_result)
        elif current_step == ConversationStep.PAYMENT_AMOUNT:
            return await self._handle_call_closing()
        else:
            return await self._handle_call_closing()
    
    def _reset_retry_counter(self, step: str):
        """Reset retry counter for a step when successfully moving to next step."""
        retry_key = f"{step}_retry_count"
        if retry_key in self.responses:
            self.responses[retry_key] = 0
    
    def _reset_all_retry_counters(self):
        """Reset all retry counters (useful when moving to a new step)."""
        keys_to_remove = [key for key in self.responses.keys() if key.endswith("_retry_count")]
        for key in keys_to_remove:
            self.responses[key] = 0
    
    async def _get_current_question_text(self, current_step: str) -> Optional[str]:
        """Get the current question text for re-asking."""
        # PURPOSE_EXPLANATION_PART1 doesn't have a question - it's a statement, so return None
        if current_step == ConversationStep.PURPOSE_EXPLANATION_PART1:
            return None
            
        questions = {
            ConversationStep.CALL_OPENING: "Am I speaking with {customer_name}?",
            ConversationStep.CUSTOMER_VERIFICATION: "Could you please confirm {customer_name}'s availability?",
            ConversationStep.LOAN_CONFIRMATION: "Did you take the loan from L&T Finance?",
            ConversationStep.PAYMENT_CONFIRMATION: "Did you make the payment in the last month?",
            ConversationStep.PAYMENT_MADE_BY: "Who made the payment for this account?",
            ConversationStep.PAYEE_DETAILS: "Could you please provide the name and contact number?",
            ConversationStep.PAYMENT_DATE: "When did you make your last payment?",
            ConversationStep.PAYMENT_MODE: "By which mode was the payment made?",
            ConversationStep.FIELD_EXECUTIVE_DETAILS: "Could you please provide the field executive's name and contact?",
            ConversationStep.PAYMENT_REASON: "What was the reason for the payment?",
            ConversationStep.VEHICLE_USER: "Who is currently using the vehicle?",
            ConversationStep.VEHICLE_STATUS: "What is the status of the vehicle?",
            ConversationStep.PAYMENT_AMOUNT: "What was the actual amount paid?",
        }
        
        question_template = questions.get(current_step)
        if question_template and self.customer_data:
            return question_template.format(
                customer_name=format_customer_name(self.customer_data.customer_name)
            )
        return question_template
    
    async def _handle_customer_verification(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[bytes, str, bool]:
        """Handle customer verification response."""
        # First try direct yes/no validation (most reliable for identity confirmation)
        is_yes = validate_yes_no_response(text)
        
        # If direct validation fails, try intent result
        if is_yes is None and intent_result and intent_result.is_expected and intent_result.extracted_value is not None:
            is_yes = intent_result.extracted_value
        
        # If still None, use LLM as fallback
        if is_yes is None:
            llm_result = await self.llm_service.classify_intent(text, ["yes", "no"], "yes_no")
            is_yes = llm_result == "yes" if llm_result else None
        
        print(f"[FlowManager] _handle_customer_verification - Text: '{text}', is_yes: {is_yes}")
        
        if is_yes is None:
            # This shouldn't happen if intent extraction worked, but handle it
            response_text = "I'm sorry, I didn't understand. Could you please say yes or no?"
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
            if not response_audio:
                raise Exception("Failed to synthesize audio for customer verification clarification")
            return response_audio, ConversationStep.CUSTOMER_VERIFICATION, False
        
        if is_yes:
            # Customer confirmed, proceed to purpose explanation (Part 1)
            self.call_event.current_step = ConversationStep.PURPOSE_EXPLANATION_PART1
            # Customize purpose text based on product/vehicle
            product = (self.customer_data.product or "").strip().upper() if self.customer_data else ""
            vehicle_name = (self.customer_data.asset or "").strip() if self.customer_data else ""
            if product.startswith("TW") or "TWO WHEELER" in product:
                # Two Wheeler loan – mention vehicle name if available
                if vehicle_name:
                    response_text = (
                        f"This is a survey call and we would like to note your feedback regarding the experience "
                        f"with L&T Finance of your {vehicle_name} loan."
                    )
                else:
                    response_text = (
                        "This is a survey call and we would like to note your feedback regarding the experience "
                        "with L&T Finance of your two-wheeler loan."
                    )
            else:
                # Default / PL and other products
                response_text = (
                    "This is a survey call and we would like to note your feedback regarding the experience "
                    "with L&T Finance of your personal loan."
                )
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
            if not response_audio:
                raise Exception("Failed to synthesize audio for purpose explanation")
            print(f"[FlowManager] Customer confirmed. Moving from CALL_OPENING to PURPOSE_EXPLANATION_PART1")
        else:
            # Wrong party, ask for availability or alternate contact
            self.call_event.current_step = ConversationStep.CUSTOMER_VERIFICATION
            customer_name = format_customer_name(self.customer_data.customer_name) if self.customer_data else "the customer"
            response_text = f"Could you please confirm {customer_name}'s availability? We can schedule a call at a convenient time, or if you have an alternate contact number, please provide it."
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
            if not response_audio:
                raise Exception("Failed to synthesize audio for alternate contact request")
            # Store that we're waiting for alternate contact info
            self.responses["waiting_for_alternate_contact"] = True
        
        await self._update_call_event()
        return response_audio, self.call_event.current_step, False
    
    async def _handle_alternate_contact(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[bytes, str, bool]:
        """Handle alternate contact information or scheduling."""
        import re
        # Try to extract phone number
        phone_match = re.search(r'\b\d{10}\b', text)
        if phone_match:
            self.responses["alternate_contact"] = phone_match.group(0)
        
        # Try to extract time/date mentions
        time_keywords = ["morning", "afternoon", "evening", "tomorrow", "today", "week", "am", "pm"]
        if any(keyword in text.lower() for keyword in time_keywords):
            self.responses["preferred_call_time"] = text
        
        # End call after capturing info
        response_text = "Thank you for your time. We will contact you at the provided number or at the scheduled time. Have a good day!"
        response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
        if not response_audio:
            raise Exception("Failed to synthesize audio")
        self.call_event.current_step = ConversationStep.CALL_CLOSING
        await self._end_call()
        return response_audio, ConversationStep.CALL_ENDED, True
    
    
    async def _handle_loan_confirmation(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[bytes, str, bool]:
        """Handle loan confirmation question."""
        # Use intent result if available
        if intent_result and intent_result.is_expected and intent_result.extracted_value is not None:
            is_yes = intent_result.extracted_value
        else:
            is_yes = validate_yes_no_response(text)
            if is_yes is None:
                llm_result = await self.llm_service.classify_intent(text, ["yes", "no"], "yes_no")
                is_yes = llm_result == "yes" if llm_result else None
        
        if is_yes is None:
            response_text = "I'm sorry, I didn't understand. Did you take the loan from L&T Finance? Please say yes or no."
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
            if not response_audio:
                raise Exception("Failed to synthesize audio for loan confirmation clarification")
            return response_audio, ConversationStep.LOAN_CONFIRMATION, False
        
        self.responses["took_loan"] = is_yes
        
        if not is_yes:
            # End call
            response_text = "Thank you for giving your time. Have a great day."
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
            if not response_audio:
                raise Exception("Failed to synthesize audio for call closing (loan not taken)")
            self.call_event.current_step = ConversationStep.CALL_CLOSING
            await self._end_call()
            return response_audio, ConversationStep.CALL_ENDED, True
        
        # Proceed to payment confirmation
        self.call_event.current_step = ConversationStep.PAYMENT_CONFIRMATION
        response_text = "Did you make the payment in the last month?"
        response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
        if not response_audio:
            raise Exception("Failed to synthesize audio")
        await self._update_call_event()
        return response_audio, self.call_event.current_step, False
    
    async def _handle_payment_confirmation(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[bytes, str, bool]:
        """Handle payment confirmation question."""
        # Use intent result if available
        if intent_result and intent_result.is_expected and intent_result.extracted_value is not None:
            is_yes = intent_result.extracted_value
        else:
            is_yes = validate_yes_no_response(text)
            if is_yes is None:
                llm_result = await self.llm_service.classify_intent(text, ["yes", "no"], "yes_no")
                is_yes = llm_result == "yes" if llm_result else None
        
        if is_yes is None:
            response_text = "I'm sorry, I didn't understand. Did you make the payment in the last month? Please say yes or no."
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
            if not response_audio:
                raise Exception("Failed to synthesize audio for payment confirmation clarification")
            return response_audio, ConversationStep.PAYMENT_CONFIRMATION, False
        
        self.responses["made_payment_last_month"] = is_yes
        
        # Check compliance
        file_has_payment = self.customer_data.payment_amt is not None and self.customer_data.payment_amt > 0
        is_compliant, note = check_payment_compliance(is_yes, file_has_payment)
        
        if not is_compliant:
            self.compliance_notes.append(note)
            response_text = "Thank you for your valuable feedback and for giving your time. Have a great day."
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
            self.call_event.current_step = ConversationStep.CALL_CLOSING
            await self._end_call()
            return response_audio, ConversationStep.CALL_ENDED, True
        
        # Proceed to who made payment
        self.call_event.current_step = ConversationStep.PAYMENT_MADE_BY
        response_text = "Who made the payment for this account? Was it you yourself, a family member, a friend, or a third party?"
        response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
        if not response_audio:
            raise Exception("Failed to synthesize audio for payment made by question")
        await self._update_call_event()
        return response_audio, self.call_event.current_step, False
    
    async def _handle_payment_made_by(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[bytes, str, bool]:
        """Handle who made the payment question."""
        # Use intent result if available
        if intent_result and intent_result.is_expected and intent_result.extracted_value:
            payer = intent_result.extracted_value
        else:
            payer = validate_payment_made_by(text)
            if not payer:
                # Try LLM
                options = ["self", "family", "friend", "third_party"]
                payer = await self.llm_service.classify_intent(text, options, "choice")
        
        if not payer:
            response_text = "I'm sorry, I didn't understand. Who made the payment? Was it you yourself, a family member, a friend, or a third party?"
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
            if not response_audio:
                raise Exception("Failed to synthesize audio for payment made by clarification")
            return response_audio, ConversationStep.PAYMENT_MADE_BY, False
        
        self.responses["payment_made_by"] = payer
        
        if payer == "self":
            # Proceed directly to payment date
            self.call_event.current_step = ConversationStep.PAYMENT_DATE
            response_text = "When did you make your last payment?"
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
            if not response_audio:
                raise Exception("Failed to synthesize audio for payment date question")
        else:
            # Need payee details
            self.call_event.current_step = ConversationStep.PAYEE_DETAILS
            response_text = "Could you please provide the name and contact number of the person who made the payment?"
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
        
        await self._update_call_event()
        return response_audio, self.call_event.current_step, False
    
    async def _handle_payee_details_or_next(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[bytes, str, bool]:
        """Handle payee details collection."""
        # Extract name and contact from text (simple extraction)
        # In production, use NER or ask separately
        # For now, store the full text and proceed
        self.responses["payee_response"] = text
        
        # Try to extract phone number
        import re
        phone_match = re.search(r'\b\d{10}\b', text)
        if phone_match:
            self.responses["payee_contact"] = phone_match.group(0)
        
        # Extract name (everything before phone number or first few words)
        words = text.split()
        if phone_match:
            name_words = text[:phone_match.start()].strip().split()
        else:
            name_words = words[:3]  # First 3 words as name
        
        if name_words:
            self.responses["payee_name"] = " ".join(name_words)
        
        # Proceed to payment date
        self.call_event.current_step = ConversationStep.PAYMENT_DATE
        response_text = "When did you make your last payment?"
        response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
        if not response_audio:
            raise Exception("Failed to synthesize audio")
        await self._update_call_event()
        return response_audio, self.call_event.current_step, False
    
    async def _handle_payment_date(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[bytes, str, bool]:
        """Handle payment date question."""
        print(f"[FlowManager] _handle_payment_date - Text: '{text}'")
        payment_date = extract_date_from_text(text)
        print(f"[FlowManager] _handle_payment_date - Extracted date: {payment_date}")
        
        # Check if multiple dates mentioned - ask for confirmation
        import re
        date_matches = re.findall(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', text.lower())
        if len(date_matches) > 1:
            # Multiple dates found, ask for confirmation
            if "date_confirmation_attempts" not in self.responses:
                self.responses["date_confirmation_attempts"] = 0
            
            self.responses["date_confirmation_attempts"] += 1
            
            if self.responses["date_confirmation_attempts"] >= 2:
                # Use the first date found or proceed
                if payment_date:
                    self.responses["last_payment_date"] = payment_date
                else:
                    # Proceed without date
                    response_text = "I understand. Let me proceed to the next question. By which mode was the payment made? Options are: Online, UPI, NEFT, RTGS in LAN, Online or UPI to Field Executive, Cash, Branch, Outlet, or NACH which is auto debit from account."
                    response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
                    self.call_event.current_step = ConversationStep.PAYMENT_MODE
                    await self._update_call_event()
                    return response_audio, self.call_event.current_step, False
            else:
                response_text = "I heard multiple dates. Could you please confirm the exact date when you made the payment?"
                response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
                return response_audio, ConversationStep.PAYMENT_DATE, False
        
        if not payment_date:
            print(f"[FlowManager] _handle_payment_date - No date extracted from text: '{text}'")
            # Ask for confirmation or try again
            if "date_attempts" not in self.responses:
                self.responses["date_attempts"] = 0
            
            self.responses["date_attempts"] += 1
            
            if self.responses["date_attempts"] >= 2:
                # Proceed without date
                response_text = "I understand. Let me proceed to the next question. By which mode was the payment made? Options are: Online, UPI, NEFT, RTGS in LAN, Online or UPI to Field Executive, Cash, Branch, Outlet, or NACH which is auto debit from account."
                response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
                self.call_event.current_step = ConversationStep.PAYMENT_MODE
                await self._update_call_event()
                return response_audio, self.call_event.current_step, False
            else:
                response_text = "Could you please confirm the exact date when you made the payment?"
                response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
                return response_audio, ConversationStep.PAYMENT_DATE, False
        
        self.responses["last_payment_date"] = payment_date
        
        # Check date compliance
        if self.customer_data and self.customer_data.deposition_date:
            is_compliant, note = check_date_compliance(
                payment_date,
                self.customer_data.deposition_date
            )
            if not is_compliant:
                self.compliance_notes.append(note)
        
        # Proceed to payment mode
        self.call_event.current_step = ConversationStep.PAYMENT_MODE
        response_text = "By which mode was the payment made? Options are: Online, UPI, NEFT, RTGS in LAN, Online or UPI to Field Executive, Cash, Branch, Outlet, or NACH which is auto debit from account."
        response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
        if not response_audio:
            raise Exception("Failed to synthesize audio")
        await self._update_call_event()
        return response_audio, self.call_event.current_step, False
    
    async def _handle_payment_mode(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[bytes, str, bool]:
        """Handle payment mode question."""
        # Use intent result if available
        if intent_result and intent_result.is_expected and intent_result.extracted_value:
            payment_mode = intent_result.extracted_value
        else:
            payment_mode = validate_payment_mode(text)
            if not payment_mode:
                # Try LLM
                options = ["online", "upi", "neft", "rtgs", "cash", "branch", "outlet", "nach", "field_executive"]
                payment_mode = await self.llm_service.classify_intent(text, options, "choice")
        
        if not payment_mode:
            response_text = "I'm sorry, I didn't understand. By which mode was the payment made? Please choose from: Online, UPI, NEFT, RTGS, Cash, Branch, Outlet, or NACH."
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
            return response_audio, ConversationStep.PAYMENT_MODE, False
        
        # Check if it's UPI/Cash to Field Executive (check text for field executive mention)
        text_lower = text.lower()
        is_field_executive_payment = (
            payment_mode in ["upi", "cash"] and 
            ("field executive" in text_lower or "field officer" in text_lower or "agent" in text_lower or "executive" in text_lower)
        )
        
        # Store payment mode - if it's UPI/Cash to field executive, mark as field_executive
        if is_field_executive_payment:
            self.responses["payment_mode"] = "field_executive"
            payment_mode_for_compliance = "field_executive"
        else:
            self.responses["payment_mode"] = payment_mode
            payment_mode_for_compliance = payment_mode
        
        # Check compliance
        is_compliant, note = check_payment_mode_compliance(payment_mode_for_compliance)
        if not is_compliant:
            self.compliance_notes.append(note)
        
        # Handle field executive payment (UPI/Cash to Field Executive) - Non-Compliance
        if payment_mode_for_compliance == "field_executive":
            # Need field executive details
            self.call_event.current_step = ConversationStep.FIELD_EXECUTIVE_DETAILS
            response_text = "Could you please provide the name and contact number of the field executive?"
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
        elif payment_mode == "cash":
            # Cash is non-compliant, but continue
            self.call_event.current_step = ConversationStep.PAYMENT_REASON
            response_text = "What was the reason for the payment? Was it for EMI, EMI plus charges, Settlement, Foreclosure, Charges, Loan cancellation, or Advance EMI?"
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
        else:
            # Compliant modes (Online/UPI/NEFT/RTGS in LAN, Branch/Outlet/NACH), proceed to reason
            self.call_event.current_step = ConversationStep.PAYMENT_REASON
            response_text = "What was the reason for the payment? Was it for EMI, EMI plus charges, Settlement, Foreclosure, Charges, Loan cancellation, or Advance EMI?"
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
        
        await self._update_call_event()
        return response_audio, self.call_event.current_step, False
    
    async def _handle_field_executive_details(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[bytes, str, bool]:
        """Handle field executive details collection."""
        # Extract name and contact
        import re
        phone_match = re.search(r'\b\d{10}\b', text)
        if phone_match:
            self.responses["field_executive_contact"] = phone_match.group(0)
        
        words = text.split()
        if phone_match:
            name_words = text[:phone_match.start()].strip().split()
        else:
            name_words = words[:3]
        
        if name_words:
            self.responses["field_executive_name"] = " ".join(name_words)
        
        # Proceed to payment reason
        self.call_event.current_step = ConversationStep.PAYMENT_REASON
        response_text = "What was the reason for the payment? Was it for EMI, EMI plus charges, Settlement, Foreclosure, Charges, Loan cancellation, or Advance EMI?"
        response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
        if not response_audio:
            raise Exception("Failed to synthesize audio")
        await self._update_call_event()
        return response_audio, self.call_event.current_step, False
    
    
    async def _handle_payment_reason(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[bytes, str, bool]:
        """Handle payment reason question."""
        # Use intent result if available
        if intent_result and intent_result.is_expected and intent_result.extracted_value:
            reason = intent_result.extracted_value
        else:
            reason = validate_payment_reason(text)
            if not reason:
                # Try LLM
                options = ["emi", "emi+charges", "settlement", "foreclosure", "charges", "loan_cancellation", "advance_emi"]
                reason = await self.llm_service.classify_intent(text, options, "choice")
        
        if not reason:
            response_text = "I'm sorry, I didn't understand. What was the reason for the payment? Please choose from: EMI, EMI plus charges, Settlement, Foreclosure, Charges, Loan cancellation, or Advance EMI."
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
            return response_audio, ConversationStep.PAYMENT_REASON, False
        
        self.responses["payment_reason"] = reason
        
        # Decide next step based on product:
        # - For Two Wheeler (TW) loans → ask additional vehicle questions
        # - For PL / others → proceed directly to amount
        product = (self.customer_data.product or "").strip().upper() if self.customer_data else ""
        if product.startswith("TW") or "TWO WHEELER" in product:
            # TW-only follow-up questions
            self.call_event.current_step = ConversationStep.VEHICLE_USER
            response_text = (
                "Who is currently using the vehicle? "
                "You can say: Customer self, Relative, Customer's friend, Sold to third party, Repossessed, or Vehicle surrendered."
            )
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
            if not response_audio:
                raise Exception("Failed to synthesize audio")
            await self._update_call_event()
            return response_audio, self.call_event.current_step, False
        else:
            # Default path – proceed to amount
            self.call_event.current_step = ConversationStep.PAYMENT_AMOUNT
            response_text = "What was the actual amount paid?"
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
            if not response_audio:
                raise Exception("Failed to synthesize audio")
            await self._update_call_event()
            return response_audio, self.call_event.current_step, False

    async def _handle_vehicle_user(
        self,
        text: str,
        intent_result = None
    ) -> Tuple[bytes, str, bool]:
        """Handle TW-only question: who is currently using the vehicle."""
        # For now, capture free-text response
        self.responses["vehicle_user"] = text.strip()
        
        self.call_event.current_step = ConversationStep.VEHICLE_STATUS
        response_text = (
            "What is the status of the vehicle? "
            "You can say: Repossessed, Surrendered at dealership or L&T Finance branch, "
            "Accidental case, Currently in use, In police custody, Vehicle stolen, or Currently not in use."
        )
        response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
        if not response_audio:
            raise Exception("Failed to synthesize audio for vehicle status question")
        await self._update_call_event()
        return response_audio, self.call_event.current_step, False

    async def _handle_vehicle_status(
        self,
        text: str,
        intent_result = None
    ) -> Tuple[bytes, str, bool]:
        """Handle TW-only question: status of the vehicle."""
        self.responses["vehicle_status"] = text.strip()
        
        # After TW-specific questions, proceed to amount
        self.call_event.current_step = ConversationStep.PAYMENT_AMOUNT
        response_text = "What was the actual amount paid?"
        response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
        if not response_audio:
            raise Exception("Failed to synthesize audio for payment amount question")
        await self._update_call_event()
        return response_audio, self.call_event.current_step, False
    
    async def _handle_payment_amount(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[bytes, str, bool]:
        """Handle payment amount question."""
        print(f"[FlowManager] _handle_payment_amount - Text: '{text}'")
        amount = extract_amount_from_text(text)
        print(f"[FlowManager] _handle_payment_amount - Extracted amount: {amount}")
        
        if not amount:
            print(f"[FlowManager] _handle_payment_amount - No amount extracted from text: '{text}'")
            response_text = "I'm sorry, I didn't catch the amount. Could you please tell me the actual amount paid?"
            response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
            return response_audio, ConversationStep.PAYMENT_AMOUNT, False
        
        self.responses["actual_amount_paid"] = float(amount)
        
        # Check amount compliance
        if self.customer_data and self.customer_data.payment_amt:
            is_compliant, note = check_amount_compliance(
                Decimal(str(amount)),
                self.customer_data.payment_amt
            )
            if not is_compliant:
                self.compliance_notes.append(note)
        
        # Proceed to closing
        return await self._handle_call_closing()
    
    async def _handle_call_closing(self) -> Tuple[bytes, str, bool]:
        """Handle call closing."""
        response_text = "Thank you for your valuable feedback and for giving your time. Have a great day."
        response_audio, _ = await self.tts_service.synthesize_with_retry(response_text)
        if not response_audio:
            raise Exception("Failed to synthesize audio")
        await self._end_call()
        return response_audio, ConversationStep.CALL_ENDED, True
    
    # Text-based handler methods (for text-to-text conversations)
    async def _handle_customer_verification_text(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[str, str, bool]:
        """Handle customer verification response (text version)."""
        is_yes = validate_yes_no_response(text)
        
        if is_yes is None and intent_result and intent_result.is_expected and intent_result.extracted_value is not None:
            is_yes = intent_result.extracted_value
        
        if is_yes is None:
            llm_result = await self.llm_service.classify_intent(text, ["yes", "no"], "yes_no")
            is_yes = llm_result == "yes" if llm_result else None
        
        if is_yes is None:
            response_text = "I'm sorry, I didn't understand. Could you please say yes or no?"
            return response_text, ConversationStep.CUSTOMER_VERIFICATION, False
        
        if is_yes:
            self.call_event.current_step = ConversationStep.PURPOSE_EXPLANATION_PART1
            response_text = "This is a survey call and we would like to note your feedback regarding the experience with L&T Finance of your personal loan."
            print(f"[FlowManager] Customer confirmed. Moving from CALL_OPENING to PURPOSE_EXPLANATION_PART1")
        else:
            self.call_event.current_step = ConversationStep.CUSTOMER_VERIFICATION
            customer_name = format_customer_name(self.customer_data.customer_name) if self.customer_data else "the customer"
            response_text = f"Could you please confirm {customer_name}'s availability? We can schedule a call at a convenient time, or if you have an alternate contact number, please provide it."
            self.responses["waiting_for_alternate_contact"] = True
        
        await self._update_call_event()
        return response_text, self.call_event.current_step, False
    
    async def _handle_alternate_contact_text(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[str, str, bool]:
        """Handle alternate contact information or scheduling (text version)."""
        import re
        phone_match = re.search(r'\b\d{10}\b', text)
        if phone_match:
            self.responses["alternate_contact"] = phone_match.group(0)
        
        time_keywords = ["morning", "afternoon", "evening", "tomorrow", "today", "week", "am", "pm"]
        if any(keyword in text.lower() for keyword in time_keywords):
            self.responses["preferred_call_time"] = text
        
        response_text = "Thank you for your time. We will contact you at the provided number or at the scheduled time. Have a good day!"
        self.call_event.current_step = ConversationStep.CALL_CLOSING
        await self._end_call()
        return response_text, ConversationStep.CALL_ENDED, True
    
    async def _handle_loan_confirmation_text(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[str, str, bool]:
        """Handle loan confirmation question (text version)."""
        if intent_result and intent_result.is_expected and intent_result.extracted_value is not None:
            is_yes = intent_result.extracted_value
        else:
            is_yes = validate_yes_no_response(text)
            if is_yes is None:
                llm_result = await self.llm_service.classify_intent(text, ["yes", "no"], "yes_no")
                is_yes = llm_result == "yes" if llm_result else None
        
        if is_yes is None:
            response_text = "I'm sorry, I didn't understand. Did you take the loan from L&T Finance? Please say yes or no."
            return response_text, ConversationStep.LOAN_CONFIRMATION, False
        
        self.responses["took_loan"] = is_yes
        
        if not is_yes:
            response_text = "Thank you for giving your time. Have a great day."
            self.call_event.current_step = ConversationStep.CALL_CLOSING
            await self._end_call()
            return response_text, ConversationStep.CALL_ENDED, True
        
        self.call_event.current_step = ConversationStep.PAYMENT_CONFIRMATION
        response_text = "Did you make the payment in the last month?"
        await self._update_call_event()
        return response_text, self.call_event.current_step, False
    
    async def _handle_payment_confirmation_text(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[str, str, bool]:
        """Handle payment confirmation question (text version)."""
        if intent_result and intent_result.is_expected and intent_result.extracted_value is not None:
            is_yes = intent_result.extracted_value
        else:
            is_yes = validate_yes_no_response(text)
            if is_yes is None:
                llm_result = await self.llm_service.classify_intent(text, ["yes", "no"], "yes_no")
                is_yes = llm_result == "yes" if llm_result else None
        
        if is_yes is None:
            response_text = "I'm sorry, I didn't understand. Did you make the payment in the last month? Please say yes or no."
            return response_text, ConversationStep.PAYMENT_CONFIRMATION, False
        
        self.responses["made_payment_last_month"] = is_yes
        
        file_has_payment = self.customer_data.payment_amt is not None and self.customer_data.payment_amt > 0
        is_compliant, note = check_payment_compliance(is_yes, file_has_payment)
        
        if not is_compliant:
            self.compliance_notes.append(note)
            response_text = "Thank you for your valuable feedback and for giving your time. Have a great day."
            self.call_event.current_step = ConversationStep.CALL_CLOSING
            await self._end_call()
            return response_text, ConversationStep.CALL_ENDED, True
        
        self.call_event.current_step = ConversationStep.PAYMENT_MADE_BY
        response_text = "Who made the payment for this account? Was it you yourself, a family member, a friend, or a third party?"
        await self._update_call_event()
        return response_text, self.call_event.current_step, False
    
    async def _handle_payment_made_by_text(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[str, str, bool]:
        """Handle who made the payment question (text version)."""
        if intent_result and intent_result.is_expected and intent_result.extracted_value:
            payer = intent_result.extracted_value
        else:
            payer = validate_payment_made_by(text)
            if not payer:
                options = ["self", "family", "friend", "third_party"]
                payer = await self.llm_service.classify_intent(text, options, "choice")
        
        if not payer:
            response_text = "I'm sorry, I didn't understand. Who made the payment? Was it you yourself, a family member, a friend, or a third party?"
            return response_text, ConversationStep.PAYMENT_MADE_BY, False
        
        self.responses["payment_made_by"] = payer
        
        if payer == "self":
            self.call_event.current_step = ConversationStep.PAYMENT_DATE
            response_text = "When did you make your last payment?"
        else:
            self.call_event.current_step = ConversationStep.PAYEE_DETAILS
            response_text = "Could you please provide the name and contact number of the person who made the payment?"
        
        await self._update_call_event()
        return response_text, self.call_event.current_step, False
    
    async def _handle_payee_details_or_next_text(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[str, str, bool]:
        """Handle payee details collection (text version)."""
        self.responses["payee_response"] = text
        
        import re
        phone_match = re.search(r'\b\d{10}\b', text)
        if phone_match:
            self.responses["payee_contact"] = phone_match.group(0)
        
        words = text.split()
        if phone_match:
            name_words = text[:phone_match.start()].strip().split()
        else:
            name_words = words[:3]
        
        if name_words:
            self.responses["payee_name"] = " ".join(name_words)
        
        self.call_event.current_step = ConversationStep.PAYMENT_DATE
        response_text = "When did you make your last payment?"
        await self._update_call_event()
        return response_text, self.call_event.current_step, False
    
    async def _handle_payment_date_text(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[str, str, bool]:
        """Handle payment date question (text version)."""
        payment_date = extract_date_from_text(text)
        print(f"[FlowManager] _handle_payment_date_text - Text: '{text}', Extracted date: {payment_date}")
        
        import re
        date_matches = re.findall(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', text.lower())
        if len(date_matches) > 1:
            if "date_confirmation_attempts" not in self.responses:
                self.responses["date_confirmation_attempts"] = 0
            
            self.responses["date_confirmation_attempts"] += 1
            
            if self.responses["date_confirmation_attempts"] >= 2:
                if payment_date:
                    self.responses["last_payment_date"] = payment_date
                else:
                    print(f"[FlowManager] _handle_payment_date_text - No date extracted after multiple attempts, proceeding")
                    response_text = "I understand. Let me proceed to the next question. By which mode was the payment made? Options are: Online, UPI, NEFT, RTGS in LAN, Online or UPI to Field Executive, Cash, Branch, Outlet, or NACH which is auto debit from account."
                    self.call_event.current_step = ConversationStep.PAYMENT_MODE
                    await self._update_call_event()
                    return response_text, self.call_event.current_step, False
            else:
                response_text = "I heard multiple dates. Could you please confirm the exact date when you made the payment?"
                return response_text, ConversationStep.PAYMENT_DATE, False
        
        if not payment_date:
            print(f"[FlowManager] _handle_payment_date_text - No date extracted from text: '{text}'")
            if "date_attempts" not in self.responses:
                self.responses["date_attempts"] = 0
            
            self.responses["date_attempts"] += 1
            
            if self.responses["date_attempts"] >= 2:
                response_text = "I understand. Let me proceed to the next question. By which mode was the payment made? Options are: Online, UPI, NEFT, RTGS in LAN, Online or UPI to Field Executive, Cash, Branch, Outlet, or NACH which is auto debit from account."
                self.call_event.current_step = ConversationStep.PAYMENT_MODE
                await self._update_call_event()
                return response_text, self.call_event.current_step, False
            else:
                response_text = "Could you please confirm the exact date when you made the payment?"
                return response_text, ConversationStep.PAYMENT_DATE, False
        
        self.responses["last_payment_date"] = payment_date
        
        if self.customer_data and self.customer_data.deposition_date:
            is_compliant, note = check_date_compliance(
                payment_date,
                self.customer_data.deposition_date
            )
            if not is_compliant:
                self.compliance_notes.append(note)
        
        self.call_event.current_step = ConversationStep.PAYMENT_MODE
        response_text = "By which mode was the payment made? Options are: Online, UPI, NEFT, RTGS in LAN, Online or UPI to Field Executive, Cash, Branch, Outlet, or NACH which is auto debit from account."
        await self._update_call_event()
        return response_text, self.call_event.current_step, False
    
    async def _handle_payment_mode_text(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[str, str, bool]:
        """Handle payment mode question (text version)."""
        if intent_result and intent_result.is_expected and intent_result.extracted_value:
            payment_mode = intent_result.extracted_value
        else:
            payment_mode = validate_payment_mode(text)
            if not payment_mode:
                options = ["online", "upi", "neft", "rtgs", "cash", "branch", "outlet", "nach", "field_executive"]
                payment_mode = await self.llm_service.classify_intent(text, options, "choice")
        
        if not payment_mode:
            response_text = "I'm sorry, I didn't understand. By which mode was the payment made? Please choose from: Online, UPI, NEFT, RTGS, Cash, Branch, Outlet, or NACH."
            return response_text, ConversationStep.PAYMENT_MODE, False
        
        text_lower = text.lower()
        is_field_executive_payment = (
            payment_mode in ["upi", "cash"] and 
            ("field executive" in text_lower or "field officer" in text_lower or "agent" in text_lower or "executive" in text_lower)
        )
        
        if is_field_executive_payment:
            self.responses["payment_mode"] = "field_executive"
            payment_mode_for_compliance = "field_executive"
        else:
            self.responses["payment_mode"] = payment_mode
            payment_mode_for_compliance = payment_mode
        
        is_compliant, note = check_payment_mode_compliance(payment_mode_for_compliance)
        if not is_compliant:
            self.compliance_notes.append(note)
        
        if payment_mode_for_compliance == "field_executive":
            self.call_event.current_step = ConversationStep.FIELD_EXECUTIVE_DETAILS
            response_text = "Could you please provide the name and contact number of the field executive?"
        elif payment_mode == "cash":
            self.call_event.current_step = ConversationStep.PAYMENT_REASON
            response_text = "What was the reason for the payment? Was it for EMI, EMI plus charges, Settlement, Foreclosure, Charges, Loan cancellation, or Advance EMI?"
        else:
            self.call_event.current_step = ConversationStep.PAYMENT_REASON
            response_text = "What was the reason for the payment? Was it for EMI, EMI plus charges, Settlement, Foreclosure, Charges, Loan cancellation, or Advance EMI?"
        
        await self._update_call_event()
        return response_text, self.call_event.current_step, False
    
    async def _handle_field_executive_details_text(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[str, str, bool]:
        """Handle field executive details collection (text version)."""
        import re
        phone_match = re.search(r'\b\d{10}\b', text)
        if phone_match:
            self.responses["field_executive_contact"] = phone_match.group(0)
        
        words = text.split()
        if phone_match:
            name_words = text[:phone_match.start()].strip().split()
        else:
            name_words = words[:3]
        
        if name_words:
            self.responses["field_executive_name"] = " ".join(name_words)
        
        self.call_event.current_step = ConversationStep.PAYMENT_REASON
        response_text = "What was the reason for the payment? Was it for EMI, EMI plus charges, Settlement, Foreclosure, Charges, Loan cancellation, or Advance EMI?"
        await self._update_call_event()
        return response_text, self.call_event.current_step, False
    
    async def _handle_payment_reason_text(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[str, str, bool]:
        """Handle payment reason question (text version)."""
        # For text flow we reuse the same validation as audio path
        reason = validate_payment_reason(text)
        if not reason and intent_result and intent_result.is_expected and intent_result.extracted_value:
            reason = intent_result.extracted_value
        
        if not reason:
            response_text = (
                "I'm sorry, I didn't understand. What was the reason for the payment? "
                "Please choose from: EMI, EMI plus charges, Settlement, Foreclosure, Charges, "
                "Loan cancellation, or Advance EMI."
            )
            return response_text, ConversationStep.PAYMENT_REASON, False
        
        self.responses["payment_reason"] = reason

        # Decide next step based on product (same logic as audio path)
        product = (self.customer_data.product or "").strip().upper() if self.customer_data else ""
        if product.startswith("TW") or "TWO WHEELER" in product:
            # TW-only follow-up questions
            self.call_event.current_step = ConversationStep.VEHICLE_USER
            response_text = (
                "Who is currently using the vehicle? "
                "You can reply: Customer self, Relative, Customer's friend, Sold to third party, "
                "Repossessed, or Vehicle surrendered."
            )
            await self._update_call_event()
            return response_text, self.call_event.current_step, False
        else:
            # Default path – proceed to amount
            self.call_event.current_step = ConversationStep.PAYMENT_AMOUNT
            response_text = "What was the actual amount paid?"
            await self._update_call_event()
            return response_text, self.call_event.current_step, False

    async def _handle_vehicle_user_text(
        self,
        text: str,
        intent_result = None
    ) -> Tuple[str, str, bool]:
        """Handle TW-only question: who is currently using the vehicle (text version)."""
        self.responses["vehicle_user"] = text.strip()
        
        self.call_event.current_step = ConversationStep.VEHICLE_STATUS
        response_text = (
            "What is the status of the vehicle? "
            "You can reply: Repossessed, Surrendered at dealership or L&T Finance branch, "
            "Accidental case, Currently in use, In police custody, Vehicle stolen, or Currently not in use."
        )
        await self._update_call_event()
        return response_text, self.call_event.current_step, False

    async def _handle_vehicle_status_text(
        self,
        text: str,
        intent_result = None
    ) -> Tuple[str, str, bool]:
        """Handle TW-only question: status of the vehicle (text version)."""
        self.responses["vehicle_status"] = text.strip()
        
        # After TW-specific questions, proceed to amount
        self.call_event.current_step = ConversationStep.PAYMENT_AMOUNT
        response_text = "What was the actual amount paid?"
        await self._update_call_event()
        return response_text, self.call_event.current_step, False
    
    async def _handle_payment_amount_text(
        self, 
        text: str, 
        intent_result = None
    ) -> Tuple[str, str, bool]:
        """Handle payment amount question (text version)."""
        print(f"[FlowManager] _handle_payment_amount_text - Text: '{text}'")
        amount = extract_amount_from_text(text)
        print(f"[FlowManager] _handle_payment_amount_text - Extracted amount: {amount}")
        
        if not amount:
            print(f"[FlowManager] _handle_payment_amount_text - No amount extracted from text: '{text}'")
            response_text = "I'm sorry, I didn't catch the amount. Could you please tell me the actual amount paid?"
            return response_text, ConversationStep.PAYMENT_AMOUNT, False
        
        self.responses["actual_amount_paid"] = float(amount)
        
        if self.customer_data and self.customer_data.payment_amt:
            is_compliant, note = check_amount_compliance(
                Decimal(str(amount)),
                self.customer_data.payment_amt
            )
            if not is_compliant:
                self.compliance_notes.append(note)
        
        return await self._handle_call_closing_text()
    
    async def _handle_call_closing_text(self) -> Tuple[str, str, bool]:
        """Handle call closing (text version)."""
        response_text = "Thank you for your valuable feedback and for giving your time. Have a great day."
        await self._end_call()
        return response_text, ConversationStep.CALL_ENDED, True
    
    async def _update_call_event(self):
        """Update call event in database."""
        if self.call_event:
            # Reset retry counter for the new step (if step changed)
            # This prevents retry counters from carrying over between steps
            current_step = self.call_event.current_step
            # Reset retry counter for the current step when updating
            retry_key = f"{current_step}_retry_count"
            if retry_key in self.responses:
                # Only reset if we're moving to a new step (not retrying same step)
                # We'll reset it when step actually changes
                pass
            
            # Convert date objects to strings for JSON serialization
            serializable_responses = {}
            for key, value in self.responses.items():
                if isinstance(value, date):
                    serializable_responses[key] = str(value)
                elif isinstance(value, Decimal):
                    serializable_responses[key] = float(value)
                else:
                    serializable_responses[key] = value
            
            self.call_event.conversation_state = {
                "step": self.call_event.current_step,
                "responses": serializable_responses,
                "compliance_notes": self.compliance_notes,
            }
            await self.db.commit()
            await self.db.refresh(self.call_event)
    
    async def _end_call(self):
        """End the call and save feedback response."""
        if not self.call_event:
            return
        
        self.call_event.status = CallStatus.COMPLETED
        self.call_event.current_step = ConversationStep.CALL_ENDED
        self.call_event.completed_at = datetime.now()
        
        # Only save feedback response if we have meaningful data
        # (i.e., customer took loan and we got some responses)
        if self.responses.get("took_loan") is not None:
            # Determine overall compliance - True if no compliance notes, False if there are notes
            is_compliant = len(self.compliance_notes) == 0
            
            # Save feedback response (can be partial)
            feedback_response = FeedbackResponseModel(
                call_event_id=self.call_event.id,
                agreement_no=self.call_event.agreement_no,
                took_loan=self.responses.get("took_loan"),
                made_payment_last_month=self.responses.get("made_payment_last_month"),
                payment_made_by=self.responses.get("payment_made_by"),
                payee_name=self.responses.get("payee_name"),
                payee_contact=self.responses.get("payee_contact"),
                last_payment_date=self.responses.get("last_payment_date"),
                payment_mode=self.responses.get("payment_mode"),
                field_executive_name=self.responses.get("field_executive_name"),
                field_executive_contact=self.responses.get("field_executive_contact"),
                payment_reason=self.responses.get("payment_reason"),
                actual_amount_paid=Decimal(str(self.responses.get("actual_amount_paid", 0))) if self.responses.get("actual_amount_paid") else None,
                is_compliant=is_compliant,
                compliance_notes="; ".join(self.compliance_notes) if self.compliance_notes else None,
            )
            
            self.db.add(feedback_response)
        
        await self.db.commit()
        await self._update_call_event()
    
    async def close(self):
        """Close service connections."""
        await self.asr_service.close()
        await self.tts_service.close()
        await self.llm_service.close()
        # IntentService doesn't have its own connections

