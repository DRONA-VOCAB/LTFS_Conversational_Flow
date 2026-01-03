from typing import Dict, Optional
from models.conversation import (
    ConversationState, QuestionResponse, ResponseStatus, QUESTIONS
)
from services.gemini_service import analyze_response
from datetime import datetime
import json


class ConversationManager:
    def __init__(self, customer_id: int, customer_name: str):
        self.customer_id = customer_id
        self.customer_name = customer_name
        self.state = ConversationState(
            customer_id=customer_id,
            customer_name=customer_name,
            current_question=0,
            questions=[],
            conversation_history=[],
            status="active",
            start_time=datetime.now()
        )
        self.max_attempts_per_question = 3
        self.max_non_responsive_attempts = 5
        
    def get_current_question(self) -> Optional[Dict]:
        """Get the current question text"""
        if self.state.current_question < len(QUESTIONS):
            question = QUESTIONS[self.state.current_question].copy()
            # Replace customer name placeholder
            question["text"] = question["text"].format(customer_name=self.customer_name)
            return question
        return None
    
    def get_question_response_object(self) -> Optional[QuestionResponse]:
        """Get or create QuestionResponse object for current question"""
        current_q_num = self.state.current_question + 1
        
        # Find existing response object
        for qr in self.state.questions:
            if qr.question_number == current_q_num:
                return qr
        
        # Create new response object
        question = QUESTIONS[self.state.current_question]
        qr = QuestionResponse(
            question_number=current_q_num,
            question_text=question["text"].format(customer_name=self.customer_name),
            attempt_count=0
        )
        self.state.questions.append(qr)
        return qr
    
    async def process_customer_response(self, customer_audio_text: str) -> Dict:
        """Process customer response and determine next action"""
        
        if self.state.status != "active":
            return {
                "bot_text": "कॉल समाप्त हो चुकी है।",
                "should_proceed": False,
                "conversation_complete": True
            }
        
        current_question_obj = self.get_current_question()
        if not current_question_obj:
            self.state.status = "completed"
            self.state.end_time = datetime.now()
            return {
                "bot_text": "सभी प्रश्न पूछे जा चुके हैं। धन्यवाद!",
                "should_proceed": False,
                "conversation_complete": True
            }
        
        qr = self.get_question_response_object()
        qr.attempt_count += 1
        qr.timestamp = datetime.now()
        qr.customer_response = customer_audio_text
        
        # Build context for Gemini
        context = f"Customer: {self.customer_name}, Question {qr.question_number} of {len(QUESTIONS)}"
        
        # Analyze response using Gemini
        analysis = await analyze_response(
            question_number=qr.question_number,
            question_text=qr.question_text,
            customer_response=customer_audio_text,
            context=context,
            conversation_history=self.state.conversation_history
        )
        
        # Update question response
        qr.status = ResponseStatus(analysis.get("status", "clarification_needed"))
        qr.extracted_answer = analysis.get("extracted_answer", "")
        qr.confidence = analysis.get("confidence", 0.0)
        
        # Add to conversation history (simplified format)
        self.state.conversation_history.append({
            "question": qr.question_text,
            "customer_response": customer_audio_text
        })
        
        # Check for graceful exit conditions
        if qr.status in [ResponseStatus.NOT_INTERESTED, ResponseStatus.BUSY]:
            if qr.attempt_count >= 2:
                return self._handle_graceful_exit("Customer not interested or busy")
        
        if qr.status == ResponseStatus.NO_RESPONSE:
            total_no_response = sum(1 for q in self.state.questions if q.status == ResponseStatus.NO_RESPONSE)
            if total_no_response >= self.max_non_responsive_attempts:
                return self._handle_graceful_exit("Customer not responding")
        
        # Handle off-topic or clarification needed
        if qr.status == ResponseStatus.OFF_TOPIC or qr.status == ResponseStatus.CLARIFICATION_NEEDED:
            if qr.attempt_count < self.max_attempts_per_question:
                return {
                    "bot_text": analysis.get("bot_response", "कृपया प्रश्न का उत्तर दें।"),
                    "should_proceed": False,
                    "conversation_complete": False,
                    "repeat_question": True
                }
            else:
                # Max attempts reached, skip to next question
                self.state.current_question += 1
                return {
                    "bot_text": "चलिए अगले प्रश्न पर आते हैं।",
                    "should_proceed": True,
                    "conversation_complete": False
                }
        
        # Valid answer received
        if qr.status == ResponseStatus.VALID_ANSWER and analysis.get("should_proceed", False):
            # Move to next question
            self.state.current_question += 1
            
            # Check if conversation is complete
            if self.state.current_question >= len(QUESTIONS):
                self.state.status = "completed"
                self.state.end_time = datetime.now()
                return {
                    "bot_text": QUESTIONS[8]["text"],  # Closing message
                    "should_proceed": False,
                    "conversation_complete": True
                }
            
            # Get next question
            next_question = self.get_current_question()
            return {
                "bot_text": next_question["text"],
                "should_proceed": True,
                "conversation_complete": False
            }
        
        # Default: ask for clarification
        return {
            "bot_text": analysis.get("bot_response", "कृपया प्रश्न का उत्तर दें।"),
            "should_proceed": False,
            "conversation_complete": False
        }
    
    def _handle_graceful_exit(self, reason: str) -> Dict:
        """Handle graceful exit from conversation"""
        self.state.status = "terminated"
        self.state.end_time = datetime.now()
        self.state.termination_reason = reason
        
        return {
            "bot_text": "आपके कीमती समय के लिए धन्यवाद। आपका दिन शुभ हो।",
            "should_proceed": False,
            "conversation_complete": True,
            "terminated": True
        }
    
    def get_conversation_summary(self) -> Dict:
        """Get JSON summary of the conversation"""
        return {
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "status": self.state.status,
            "start_time": self.state.start_time.isoformat() if self.state.start_time else None,
            "end_time": self.state.end_time.isoformat() if self.state.end_time else None,
            "termination_reason": self.state.termination_reason,
            "questions_answered": len([q for q in self.state.questions if q.status == ResponseStatus.VALID_ANSWER]),
            "total_questions": len(QUESTIONS),
            "responses": [
                {
                    "question_number": qr.question_number,
                    "question_text": qr.question_text,
                    "customer_response": qr.customer_response,
                    "extracted_answer": qr.extracted_answer,
                    "status": qr.status.value if qr.status else None,
                    "confidence": qr.confidence,
                    "attempt_count": qr.attempt_count,
                    "timestamp": qr.timestamp.isoformat() if qr.timestamp else None
                }
                for qr in self.state.questions
            ]
        }

