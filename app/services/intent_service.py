"""Intent extraction and emotion detection service."""
from typing import Optional, Dict, Any, Tuple
import time
from app.services.llm_service import LLMService
from app.utils.validators import (
    validate_yes_no_response,
    validate_payment_mode,
    validate_payment_reason,
    validate_payment_made_by,
)


class EmotionType:
    """Emotion type constants."""
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"
    ANGRY = "angry"
    CONFUSED = "confused"
    HAPPY = "happy"
    ANXIOUS = "anxious"
    CALM = "calm"


class IntentResult:
    """Intent extraction result."""
    def __init__(
        self,
        intent: Optional[str] = None,
        confidence: float = 0.0,
        emotion: str = EmotionType.NEUTRAL,
        emotion_score: float = 0.0,
        is_expected: bool = False,
        extracted_value: Any = None,
        needs_llm_response: bool = False
    ):
        self.intent = intent
        self.confidence = confidence
        self.emotion = emotion
        self.emotion_score = emotion_score
        self.is_expected = is_expected
        self.extracted_value = extracted_value
        self.needs_llm_response = needs_llm_response


class IntentService:
    """Service for extracting intents and emotions from user responses."""
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
    
    async def extract_intent_and_emotion(
        self,
        text: str,
        current_step: str,
        expected_outcomes: list,
        context: Optional[Dict[str, Any]] = None
    ) -> IntentResult:
        """
        Extract intent and emotion from user response.
        
        Args:
            text: User's spoken text
            current_step: Current conversation step
            expected_outcomes: List of expected intents/values for this step
            context: Additional context about the conversation
        
        Returns:
            IntentResult with intent, emotion, and validation info
        """
        text_lower = text.lower().strip()
        
        # First, try to extract intent using keyword matching
        intent_result = self._extract_intent_keyword_based(text_lower, current_step, expected_outcomes)
        
        # Extract emotion
        emotion, emotion_score = await self._detect_emotion(text, context)
        
        # If intent found and matches expected, return early
        if intent_result and intent_result.is_expected:
            intent_result.emotion = emotion
            intent_result.emotion_score = emotion_score
            return intent_result
        
        # If intent not found or doesn't match expected outcomes
        # Check if we need LLM response
        needs_llm = not intent_result or not intent_result.is_expected
        
        return IntentResult(
            intent=intent_result.intent if intent_result else None,
            confidence=intent_result.confidence if intent_result else 0.0,
            emotion=emotion,
            emotion_score=emotion_score,
            is_expected=False,
            extracted_value=intent_result.extracted_value if intent_result else None,
            needs_llm_response=needs_llm
        )
    
    def _extract_intent_keyword_based(
        self,
        text: str,
        current_step: str,
        expected_outcomes: list
    ) -> Optional[IntentResult]:
        """Extract intent using keyword-based matching."""
        extracted_value = None
        intent = None
        
        # Try different validators based on step type
        if "yes_no" in str(expected_outcomes).lower() or "confirmation" in current_step.lower():
            # Yes/No question
            is_yes = validate_yes_no_response(text)
            if is_yes is not None:
                intent = "yes" if is_yes else "no"
                extracted_value = is_yes
                return IntentResult(
                    intent=intent,
                    confidence=0.9,
                    is_expected=True,
                    extracted_value=extracted_value
                )
        
        if "payment_mode" in current_step.lower():
            mode = validate_payment_mode(text)
            if mode:
                intent = mode
                extracted_value = mode
                return IntentResult(
                    intent=intent,
                    confidence=0.9,
                    is_expected=True,
                    extracted_value=extracted_value
                )
        
        if "payment_reason" in current_step.lower():
            reason = validate_payment_reason(text)
            if reason:
                intent = reason
                extracted_value = reason
                return IntentResult(
                    intent=intent,
                    confidence=0.9,
                    is_expected=True,
                    extracted_value=extracted_value
                )
        
        if "payment_made_by" in current_step.lower() or "who" in current_step.lower():
            payer = validate_payment_made_by(text)
            if payer:
                intent = payer
                extracted_value = payer
                return IntentResult(
                    intent=intent,
                    confidence=0.9,
                    is_expected=True,
                    extracted_value=extracted_value
                )
        
        return None
    
    async def _detect_emotion(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, float]:
        """
        Detect emotion from text using LLM.
        
        Returns:
            Tuple of (emotion_type, confidence_score)
        """
        # Keyword-based emotion detection first (faster, no LLM call)
        emotion_keywords = {
            EmotionType.FRUSTRATED: [
                "frustrated", "annoyed", "irritated", "fed up", "tired of",
                "boring", "waste", "time", "again", "repeatedly", "stop",
                "bas", "kitna", "ab", "ruk", "band"
            ],
            EmotionType.ANGRY: [
                "angry", "mad", "upset", "annoyed", "disgusted", "hate",
                "gussa", "naraz", "pareshan", "bekar"
            ],
            EmotionType.CONFUSED: [
                "confused", "don't understand", "unclear", "what", "how",
                "samajh", "nahi", "kya", "kaise", "kab"
            ],
            EmotionType.ANXIOUS: [
                "worried", "anxious", "nervous", "concerned", "scared",
                "chinta", "tension", "darr"
            ],
            EmotionType.HAPPY: [
                "happy", "glad", "pleased", "thankful", "good", "great",
                "accha", "theek", "sahi", "badhiya"
            ],
        }
        
        text_lower = text.lower()
        
        # Check for emotion keywords
        for emotion_type, keywords in emotion_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return emotion_type, 0.8
        
        # If no clear emotion detected, use LLM for deeper analysis
        try:
            prompt = f"""Analyze the emotion in this user response. Respond with ONLY one word from: neutral, frustrated, angry, confused, happy, anxious, calm

User response: "{text}"

Emotion:"""
            
            result = await self.llm_service.generate_response(prompt)
            
            if result:
                emotion_lower = result.strip().lower()
                for emotion_type in [
                    EmotionType.FRUSTRATED, EmotionType.ANGRY, EmotionType.CONFUSED,
                    EmotionType.HAPPY, EmotionType.ANXIOUS, EmotionType.CALM, EmotionType.NEUTRAL
                ]:
                    if emotion_type in emotion_lower:
                        return emotion_type, 0.7
            
        except Exception as e:
            print(f"[IntentService] Error detecting emotion: {e}")
        
        return EmotionType.NEUTRAL, 0.5
    
    async def generate_empathetic_response(
        self,
        user_text: str,
        emotion: str,
        current_step: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate empathetic, human-like response based on emotion and context.
        
        Args:
            user_text: User's response
            emotion: Detected emotion
            current_step: Current conversation step
            context: Additional context
        
        Returns:
            Friendly, empathetic response text
        """
        # Build context-aware prompt
        step_context = self._get_step_context(current_step)
        
        emotion_guidance = {
            EmotionType.FRUSTRATED: "The user seems frustrated. Calm them down, acknowledge their frustration, apologize if needed, and be very patient and understanding. Keep the response short and reassuring.",
            EmotionType.ANGRY: "The user seems angry. Be extremely calm, apologetic, and understanding. Acknowledge their concern and try to resolve it quickly.",
            EmotionType.CONFUSED: "The user seems confused. Be very clear, patient, and explain things simply. Break down the question if needed.",
            EmotionType.ANXIOUS: "The user seems anxious or worried. Be reassuring, calm, and supportive. Let them know everything is okay.",
            EmotionType.HAPPY: "The user seems happy and cooperative. Match their positive energy, be friendly and warm.",
            EmotionType.NEUTRAL: "Respond in a friendly, natural, human manner. Be conversational and warm.",
            EmotionType.CALM: "The user is calm. Respond naturally and continue the conversation smoothly.",
        }
        
        guidance = emotion_guidance.get(emotion, emotion_guidance[EmotionType.NEUTRAL])
        
        start_time = time.perf_counter()
        prompt = f"""You are a friendly, empathetic customer service representative for L&T Finance conducting a feedback survey call. You speak naturally and humanly, like a real person would.

Current situation:
- Current step: {current_step}
- Step context: {step_context}
- User's response: "{user_text}"
- User's emotion: {emotion}

Guidance: {guidance}

Generate a natural, empathetic, human-like response that:
1. Acknowledges the user's emotion appropriately (don't be robotic)
2. Addresses their concern or confusion naturally
3. Is warm, friendly, and conversational - sound like a real person
4. Is concise (1-2 sentences max)
5. Sounds natural when spoken aloud (avoid formal language)
6. Uses natural speech patterns and contractions (I'm, don't, etc.)
7. DO NOT ask any new questions - only acknowledge and reassure. The system will re-ask the current question automatically.

CRITICAL: Do NOT ask for name, contact number, or any other details. Only provide empathetic acknowledgment. The system will handle asking the appropriate question.

Important: Be genuinely empathetic. If the user is frustrated, show real understanding. If confused, be patient and clear. Sound human, not like a robot.

Response (just the response text, no quotes or explanations):"""
        
        response = await self.llm_service.generate_response(prompt)
        latency = time.perf_counter() - start_time
        
        if response:
            # Clean up the response
            response = response.strip()
            # Remove quotes if present
            if response.startswith('"') and response.endswith('"'):
                response = response[1:-1]
            print(f"[IntentService] generate_empathetic_response latency: {latency:.3f}s, emotion: {emotion}, response length: {len(response)} chars")
            return response
        
        # Fallback response
        fallback_responses = {
            EmotionType.FRUSTRATED: "I completely understand your concern. Let me help you with this. Could you please help me with a quick question?",
            EmotionType.ANGRY: "I apologize for any inconvenience. Let me make this quick and easy for you.",
            EmotionType.CONFUSED: "No worries at all! Let me explain this more clearly.",
            EmotionType.ANXIOUS: "Don't worry, everything is fine. This is just a quick survey.",
            EmotionType.HAPPY: "Great! Let's continue with the next question.",
            EmotionType.NEUTRAL: "I understand. Let me help you with that.",
        }
        
        return fallback_responses.get(emotion, "I understand. Could you please help me with this?")
    
    def _get_step_context(self, current_step: str) -> str:
        """Get human-readable context for the current step."""
        step_contexts = {
            "call_opening": "Opening the call and verifying customer identity",
            "customer_verification": "Verifying if we're speaking with the right person",
            "purpose_explanation": "Explaining the purpose of the survey call",
            "loan_confirmation": "Asking if the customer took a loan from L&T Finance",
            "payment_confirmation": "Asking if payment was made in the last month",
            "payment_made_by": "Asking who made the payment",
            "payment_date": "Asking when the payment was made",
            "payment_mode": "Asking about the payment method used",
            "payment_reason": "Asking the reason for the payment",
            "payment_amount": "Asking about the payment amount",
            "call_closing": "Closing the call with thank you message",
        }
        
        return step_contexts.get(current_step, "Conducting survey questions")

