from typing import Dict, Optional
from models.conversation import (
    ConversationState,
    QuestionResponse,
    ResponseStatus,
    QUESTIONS,
)
from services.gemini_service import analyze_response
from datetime import datetime


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
            start_time=datetime.now(),
        )
        self.max_attempts_per_question = 3
        self.max_non_responsive_attempts = 5

    def get_current_question(
        self, question_index: Optional[float] = None
    ) -> Optional[Dict]:
        """Get the current question text by index or current question number"""
        if question_index is None:
            question_index = self.state.current_question

        # If question_index is an integer, treat it as an index into QUESTIONS array
        if isinstance(question_index, int) and 0 <= question_index < len(QUESTIONS):
            question = QUESTIONS[question_index].copy()
            question["text"] = question["text"].format(customer_name=self.customer_name)
            return question

        # Otherwise, find question by number (can be int or float like 1.1, 4.1, etc.)
        for q in QUESTIONS:
            if q["number"] == question_index:
                question = q.copy()
                # Replace customer name placeholder
                question["text"] = question["text"].format(
                    customer_name=self.customer_name
                )
                return question

        return None

    def find_question_by_number(self, question_number: float) -> Optional[Dict]:
        """Find a question by its number (supports float numbers like 1.1, 4.1)"""
        for q in QUESTIONS:
            if q["number"] == question_number:
                question = q.copy()
                question["text"] = question["text"].format(
                    customer_name=self.customer_name
                )
                return question
        return None

    def get_question_response_object(
        self, question_number: Optional[float] = None
    ) -> Optional[QuestionResponse]:
        """Get or create QuestionResponse object for current question"""
        if question_number is None:
            # Get current question number
            current_q = self.get_current_question()
            if current_q:
                question_number = current_q["number"]
            else:
                return None

        # Find existing response object
        for qr in self.state.questions:
            if qr.question_number == question_number:
                return qr

        # Create new response object
        question = self.find_question_by_number(question_number)
        if not question:
            return None

        qr = QuestionResponse(
            question_number=question_number,
            question_text=question["text"],
            attempt_count=0,
        )
        self.state.questions.append(qr)
        return qr

    async def process_customer_response(self, customer_audio_text: str) -> Dict:
        """Process customer response and determine next action"""
        import logging

        logger = logging.getLogger(__name__)

        print(f"\n{'='*80}")
        print(f"📋 CONVERSATION MANAGER - Processing Response")
        print(f"   Customer: {self.customer_name}")
        print(f"   User input: '{customer_audio_text}'")
        print(f"   Current status: {self.state.status}")
        print(f"   Current question: {self.state.current_question}")
        print(f"{'='*80}\n")
        logger.info(f"📋 Processing customer response: '{customer_audio_text}'")

        if self.state.status != "active":
            print(f"⚠️ Conversation not active, status: {self.state.status}")
            return {
                "bot_text": "कॉल समाप्त हो चुकी है।",
                "should_proceed": False,
                "conversation_complete": True,
            }

        current_q = self.get_current_question()
        if not current_q:
            self.state.status = "completed"
            self.state.end_time = datetime.now()
            return {
                "bot_text": "सभी प्रश्न पूछे जा चुके हैं। धन्यवाद!",
                "should_proceed": False,
                "conversation_complete": True,
            }

        qr = self.get_question_response_object(current_q["number"])
        qr.attempt_count += 1
        qr.timestamp = datetime.now()
        qr.customer_response = customer_audio_text

        print(f"   Question {qr.question_number}: '{qr.question_text}'")
        print(f"   Attempt: {qr.attempt_count}")
        logger.info(f"   Question {qr.question_number}, Attempt {qr.attempt_count}")

        # Build context for Gemini
        context = f"Customer: {self.customer_name}, Question {qr.question_number}"

        # Analyze response using Gemini with question-specific prompt
        print(f"\n{'='*80}")
        print(f"🤖 SENDING TO GEMINI FOR ANALYSIS...")
        print(f"   Question Number: {qr.question_number}")
        print(f"   Question: '{qr.question_text}'")
        print(f"   Customer response: '{customer_audio_text}'")
        print(f"{'='*80}\n")
        logger.info(
            f"🤖 Sending to Gemini for analysis (Question {qr.question_number})"
        )

        analysis = await analyze_response(
            question_number=qr.question_number,
            question_text=qr.question_text,
            customer_response=customer_audio_text,
            context=context,
            conversation_history=self.state.conversation_history,
        )

        print(f"\n{'='*80}")
        print(f"🤖 GEMINI ANALYSIS RESULT:")
        print(f"   Status: {analysis.get('status')}")
        print(f"   Confidence: {analysis.get('confidence', 0):.2f}")
        print(f"   Should proceed: {analysis.get('should_proceed', False)}")
        print(f"   Bot response: '{analysis.get('bot_response', '')}'")
        print(f"{'='*80}\n")
        logger.info(
            f"🤖 Gemini analysis: status={analysis.get('status')}, proceed={analysis.get('should_proceed')}"
        )

        # Update question response
        qr.status = ResponseStatus(analysis.get("status", "clarification_needed"))
        qr.extracted_answer = analysis.get("extracted_answer", "")
        qr.confidence = analysis.get("confidence", 0.0)

        # Add to conversation history (simplified format)
        self.state.conversation_history.append(
            {"question": qr.question_text, "customer_response": customer_audio_text}
        )

        # Check for graceful exit conditions
        if qr.status in [ResponseStatus.NOT_INTERESTED, ResponseStatus.BUSY]:
            if qr.attempt_count >= 2:
                return self._handle_graceful_exit("Customer not interested or busy")

        if qr.status == ResponseStatus.NO_RESPONSE:
            total_no_response = sum(
                1
                for q in self.state.questions
                if q.status == ResponseStatus.NO_RESPONSE
            )
            if total_no_response >= self.max_non_responsive_attempts:
                return self._handle_graceful_exit("Customer not responding")

        # Handle off-topic or clarification needed - use LLM's bot_response
        if (
            qr.status == ResponseStatus.OFF_TOPIC
            or qr.status == ResponseStatus.CLARIFICATION_NEEDED
        ):
            if qr.attempt_count < self.max_attempts_per_question:
                return {
                    "bot_text": analysis.get("bot_response", "कृपया प्रश्न का उत्तर दें।"),
                    "should_proceed": False,
                    "conversation_complete": False,
                }
            else:
                # Max attempts reached - let LLM decide next question or end gracefully
                next_question_num_str = analysis.get("next_question", "")
                if next_question_num_str and next_question_num_str.lower() != "end":
                    try:
                        next_question_num = float(next_question_num_str)
                        next_question = self.find_question_by_number(next_question_num)
                        if next_question:
                            # Update current question index
                            for idx, q in enumerate(QUESTIONS):
                                if q["number"] == next_question_num:
                                    self.state.current_question = idx
                                    break
                            return {
                                "bot_text": next_question["text"],
                                "should_proceed": True,
                                "conversation_complete": False,
                            }
                    except (ValueError, TypeError):
                        pass

                # Fallback: graceful exit
                return self._handle_graceful_exit("Max attempts reached for question")

        # Valid answer received - proceed to next question without acknowledgment
        if qr.status == ResponseStatus.VALID_ANSWER and analysis.get(
            "should_proceed", False
        ):
            # Get next question number from LLM response (for branching like 1.1, 4.1, 6.1)
            next_question_num_str = analysis.get("next_question", "")

            # Handle "end" or empty next_question
            if next_question_num_str.lower() == "end" or not next_question_num_str:
                self.state.status = "completed"
                self.state.end_time = datetime.now()
                # Find closing message
                closing_q = self.find_question_by_number(
                    9
                ) or self.find_question_by_number(1.2)
                closing_text = (
                    closing_q["text"]
                    if closing_q
                    else "आपके मूल्यवान फ़ीडबैक और समय देने के लिए धन्यवाद। आपका दिन शुभ हो।"
                )
                return {
                    "bot_text": closing_text,
                    "should_proceed": False,
                    "conversation_complete": True,
                }

            # Find current question index
            current_idx = None
            for idx, q in enumerate(QUESTIONS):
                if q["number"] == qr.question_number:
                    current_idx = idx
                    break

            if current_idx is None:
                # Current question not found - end conversation
                self.state.status = "completed"
                self.state.end_time = datetime.now()
                closing_q = self.find_question_by_number(
                    9
                ) or self.find_question_by_number(1.2)
                closing_text = (
                    closing_q["text"]
                    if closing_q
                    else "आपके मूल्यवान फ़ीडबैक और समय देने के लिए धन्यवाद। आपका दिन शुभ हो।"
                )
                return {
                    "bot_text": closing_text,
                    "should_proceed": False,
                    "conversation_complete": True,
                }

            # Determine next question number based on question-specific logic
            # Special handling for branching questions: 1 (yes/no), 4 (options), 6 (options)
            next_question_num = None
            extracted_answer = qr.extracted_answer or ""

            # Get the next sequential question (for fallback)
            sequential_next = (
                QUESTIONS[current_idx + 1]["number"]
                if current_idx + 1 < len(QUESTIONS)
                else None
            )

            # Handle Question 1: Yes → 2, No → 1.1
            if qr.question_number == 1:
                if extracted_answer == "yes":
                    # Yes answer → go to question 2 (skip 1.1)
                    next_question_num = 2
                    logger.info(f"✅ Question 1: 'yes' answer → going to question 2")
                elif extracted_answer == "no":
                    # No answer → go to question 1.1 (sequential)
                    next_question_num = 1.1
                    logger.info(f"✅ Question 1: 'no' answer → going to question 1.1")
                else:
                    # Invalid answer - use LLM's suggestion or sequential
                    try:
                        llm_next = float(next_question_num_str)
                        if self.find_question_by_number(llm_next):
                            next_question_num = llm_next
                    except (ValueError, TypeError):
                        pass
                    if next_question_num is None:
                        next_question_num = sequential_next

            # Handle Question 4: Option 1 → 5, Options 2,3,4 → 4.1
            elif qr.question_number == 4:
                if extracted_answer == "1":
                    next_question_num = 5
                    logger.info(f"✅ Question 4: option 1 → going to question 5")
                elif extracted_answer in ["2", "3", "4"]:
                    next_question_num = 4.1
                    logger.info(
                        f"✅ Question 4: option {extracted_answer} → going to question 4.1"
                    )
                else:
                    # Use LLM's suggestion or sequential
                    try:
                        llm_next = float(next_question_num_str)
                        if self.find_question_by_number(llm_next):
                            next_question_num = llm_next
                    except (ValueError, TypeError):
                        pass
                    if next_question_num is None:
                        next_question_num = sequential_next

            # Handle Question 6: Options 1,4,5,6 → 7, Options 2,3 → 6.1
            elif qr.question_number == 6:
                if extracted_answer in ["1", "4", "5", "6"]:
                    next_question_num = 7
                    logger.info(
                        f"✅ Question 6: option {extracted_answer} → going to question 7"
                    )
                elif extracted_answer in ["2", "3"]:
                    next_question_num = 6.1
                    logger.info(
                        f"✅ Question 6: option {extracted_answer} → going to question 6.1"
                    )
                else:
                    # Use LLM's suggestion or sequential
                    try:
                        llm_next = float(next_question_num_str)
                        if self.find_question_by_number(llm_next):
                            next_question_num = llm_next
                    except (ValueError, TypeError):
                        pass
                    if next_question_num is None:
                        next_question_num = sequential_next

            # For all other questions, use LLM's next_question if valid, otherwise sequential
            else:
                try:
                    llm_next = float(next_question_num_str)
                    if self.find_question_by_number(llm_next):
                        # Only accept if it's a branch (has decimal) or matches sequential
                        is_branch = llm_next != int(llm_next)
                        matches_sequential = llm_next == sequential_next
                        if is_branch or matches_sequential:
                            next_question_num = llm_next
                        else:
                            logger.warning(
                                f"⚠️ LLM suggested question {llm_next} but current is {qr.question_number}, "
                                f"sequential next is {sequential_next}. Using sequential flow."
                            )
                except (ValueError, TypeError):
                    pass

            # If still no next question, use sequential fallback
            if next_question_num is None:
                if sequential_next is not None:
                    next_question_num = sequential_next
                else:
                    # End conversation - no more questions
                    self.state.status = "completed"
                    self.state.end_time = datetime.now()
                    closing_q = self.find_question_by_number(
                        9
                    ) or self.find_question_by_number(1.2)
                    closing_text = (
                        closing_q["text"]
                        if closing_q
                        else "आपके मूल्यवान फ़ीडबैक और समय देने के लिए धन्यवाद। आपका दिन शुभ हो।"
                    )
                    return {
                        "bot_text": closing_text,
                        "should_proceed": False,
                        "conversation_complete": True,
                    }

            # Update current question index to next question
            next_idx = None
            for idx, q in enumerate(QUESTIONS):
                if q["number"] == next_question_num:
                    next_idx = idx
                    break

            if next_idx is not None:
                self.state.current_question = next_idx
                print(f"\n{'='*80}")
                print(f"✅ UPDATED CURRENT QUESTION INDEX:")
                print(
                    f"   Previous index: {current_idx} (Question {qr.question_number})"
                )
                print(f"   New index: {next_idx} (Question {next_question_num})")
                print(f"{'='*80}\n")
                logger.info(
                    f"✅ Updated current_question index: {current_idx} → {next_idx} "
                    f"(Question {qr.question_number} → {next_question_num})"
                )
            else:
                logger.error(
                    f"❌ Could not find index for question {next_question_num}"
                )

            # Return empty bot_text to skip acknowledgment, go directly to next question
            return {
                "bot_text": "",  # Empty - no acknowledgment, go directly to next question
                "should_proceed": True,
                "conversation_complete": False,
                "next_question_number": next_question_num,
            }

        # Default: ask for clarification
        return {
            "bot_text": analysis.get("bot_response", "कृपया प्रश्न का उत्तर दें।"),
            "should_proceed": False,
            "conversation_complete": False,
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
            "terminated": True,
        }

    def get_conversation_summary(self) -> Dict:
        """Get JSON summary of the conversation"""
        return {
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "status": self.state.status,
            "start_time": (
                self.state.start_time.isoformat() if self.state.start_time else None
            ),
            "end_time": (
                self.state.end_time.isoformat() if self.state.end_time else None
            ),
            "termination_reason": self.state.termination_reason,
            "questions_answered": len(
                [
                    q
                    for q in self.state.questions
                    if q.status == ResponseStatus.VALID_ANSWER
                ]
            ),
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
                    "timestamp": qr.timestamp.isoformat() if qr.timestamp else None,
                }
                for qr in self.state.questions
            ],
        }
