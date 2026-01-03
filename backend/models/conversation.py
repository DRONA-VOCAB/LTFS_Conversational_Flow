from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class QuestionStatus(str, Enum):
    PENDING = "pending"
    ASKED = "asked"
    ANSWERED = "answered"
    SKIPPED = "skipped"


class ResponseStatus(str, Enum):
    VALID_ANSWER = "valid_answer"
    OFF_TOPIC = "off_topic"
    NOT_INTERESTED = "not_interested"
    BUSY = "busy"
    CLARIFICATION_NEEDED = "clarification_needed"
    NO_RESPONSE = "no_response"


class QuestionResponse(BaseModel):
    question_number: int
    question_text: str
    customer_response: Optional[str] = None
    extracted_answer: Optional[str] = None
    status: Optional[ResponseStatus] = None
    confidence: Optional[float] = None
    attempt_count: int = 0
    timestamp: Optional[datetime] = None


class ConversationState(BaseModel):
    customer_id: int
    customer_name: str
    current_question: int = 0
    questions: List[QuestionResponse] = []
    conversation_history: List[Dict[str, str]] = []
    status: str = "active"  # active, completed, terminated
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    termination_reason: Optional[str] = None


class CallSession(BaseModel):
    session_id: str
    customer_id: int
    customer_name: str
    conversation_state: ConversationState
    created_at: datetime


# Question definitions
QUESTIONS = [
    {
        "number": 1,
        "text": "नमस्ते, मैं L&T finance की तरफ़ से बात कर रहा हूँ, क्या मेरी बात श्रीमान / श्रीमती {customer_name} जी से हो रही है?",
        "type": "verification"
    },
    {
        "number": 2,
        "text": "मैं L&T Finance की तरफ़ से बात कर रहा हूँ। यह कॉल आपके personal loan / Two Wheeler Loan के भुगतान अनुभव को समझने के लिए है। क्या आपने L&T Finance से Loan लिया है?",
        "type": "yes_no"
    },
    {
        "number": 3,
        "text": "क्या आपने पिछले महीने भुगतान/payment किया था?",
        "type": "yes_no"
    },
    {
        "number": 4,
        "text": "इस account का भुगतान/payment किसने किया है? Options: 1. आपने स्वयं भुगतान किया। 2. किसी परिवार का सदस्य 3. ग्राहक के किसी मित्र 4. या फिर किसी और ने (third party)",
        "type": "multiple_choice"
    },
    {
        "number": 5,
        "text": "आपने अपनी पिछली भुगतान(payment) किस तारीख़ को किया था?",
        "type": "date"
    },
    {
        "number": 6,
        "text": "भुगतान (payment) किस माध्यम से किया गया था? Options: 1. ऑनलाइन / UPI / NEFT / RTGS (LAN में) 2. ऑनलाइन / UPI फ़ील्ड एग्ज़ीक्यूटिव को 3. नकद (Cash) 4. शाखा (Branch) 5. आउटलेट (Outlet) 6. NACH (Automated Payment)",
        "type": "multiple_choice"
    },
    {
        "number": 7,
        "text": "भुगतान (payment) किस कारण से किया गया था? Options: 1. ईएमआई (EMI) 2. ईएमआई + शुल्क (EMI + Charges) 3. सेटलमेंट (Settlement) 4. फोरक्लोज़र (Foreclosure) 5. शुल्क (Charges) 6. Loan रद्दीकरण (Loan Cancellation) 7. अग्रिम(advance) ईएमआई (Advance EMI)",
        "type": "multiple_choice"
    },
    {
        "number": 8,
        "text": "वास्तव में कितना भुगतान किया गया था?",
        "type": "amount"
    },
    {
        "number": 9,
        "text": "आपके मूल्यवान फ़ीडबैक और समय देने के लिए धन्यवाद। आपका दिन शुभ हो।",
        "type": "closing"
    }
]

