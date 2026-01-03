from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


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


# Question definitions with proper flow
QUESTIONS = [
    {
        "number": 1,
        "text": "नमस्ते, मैं L&T Finance की तरफ़ से बात कर रही हूँ। क्या मैं {customer_name} जी से बात कर रही हूँ?",
        "type": "verification",
        "branch_on": "yes_no"  # Yes -> Q2, No -> Q1a (availability)
    },
    {
        "number": 1.1,  # Sub-question for "No" response
        "text": "कृपया बताइए, {customer_name} जी से किस समय पर संपर्क करना उचित रहेगा? साथ ही, यदि कोई alternate नंबर उपलब्ध हो, तो कृपया share करें।",
        "type": "availability",
        "is_sub_question": True
    },
    {
        "number": 1.2,  # Closing for availability
        "text": "धन्यवाद। हम आपके द्वारा बताए गए समय या नंबर पर आपसे संपर्क करेंगे। आपके कीमती समय के लिए धन्यवाद। आपका दिन शुभ हो!",
        "type": "closing",
        "is_sub_question": True
    },
    {
        "number": 2,
        "text": "मैं L&T Finance की तरफ़ से बात कर रही हूँ। यह कॉल आपके personal loan या Two Wheeler Loan के भुगतान अनुभव को समझने के लिए है। क्या आपने L&T Finance से Loan लिया है?",
        "type": "yes_no"
    },
    {
        "number": 3,
        "text": "क्या आपने पिछले महीने भुगतान या payment किया था?",
        "type": "yes_no"
    },
    {
        "number": 4,
        "text": "इस account का भुगतान या payment किसने किया है? Options हैं: 1. आपने स्वयं भुगतान किया, 2. किसी परिवार का सदस्य, 3. ग्राहक के किसी मित्र, या 4. किसी और ने, यानी third party।",
        "type": "multiple_choice",
        "branch_on": "option"  # Option 1 -> Q5, Options 2,3,4 -> Q4a
    },
    {
        "number": 4.1,  # Sub-question for options 2,3,4
        "text": "कृपया बताइए, इस खाते का भुगतान किसने किया है? क्या मैं भुगतानकर्ता का नाम और संपर्क नंबर नोट कर सकती हूँ?",
        "type": "payer_details",
        "is_sub_question": True
    },
    {
        "number": 5,
        "text": "आपने अपनी पिछली भुगतान या payment किस तारीख़ को किया था?",
        "type": "date",
        "confirmation": "कृपया तारीख़ बताइए, ताकि हम उसे दर्ज कर सकें।"
    },
    {
        "number": 6,
        "text": "भुगतान या payment किस माध्यम से किया गया था? Options हैं: 1. ऑनलाइन, UPI, NEFT, या RTGS, LAN में, 2. ऑनलाइन या UPI, फ़ील्ड एग्ज़ीक्यूटिव को, 3. नकद या Cash, 4. शाखा या Branch, 5. आउटलेट या Outlet, 6. NACH, यानी Automated Payment।",
        "type": "multiple_choice",
        "branch_on": "option"  # Options 1,4,5,6 -> Q7, Options 2,3 -> Q6a
    },
    {
        "number": 6.1,  # Sub-question for options 2,3
        "text": "कृपया बताइए, भुगतान लेने वाले फ़ील्ड एग्ज़ीक्यूटिव का नाम क्या है? क्या मैं उनका संपर्क नंबर भी नोट कर सकती हूँ?",
        "type": "executive_details",
        "is_sub_question": True
    },
    {
        "number": 7,
        "text": "भुगतान या payment किस कारण से किया गया था? Options हैं: 1. ईएमआई या EMI, 2. ईएमआई प्लस शुल्क, यानी EMI plus Charges, 3. सेटलमेंट या Settlement, 4. फोरक्लोज़र या Foreclosure, 5. शुल्क या Charges, 6. Loan रद्दीकरण या Loan Cancellation, 7. अग्रिम ईएमआई, यानी Advance EMI।",
        "type": "multiple_choice"
    },
    {
        "number": 8,
        "text": "वास्तव में कितना भुगतान किया गया था?",
        "type": "amount",
        "confirmation": "कृपया राशि या amount बताइए, ताकि हम उसे दर्ज कर सकें।"
    },
    {
        "number": 9,
        "text": "आपके मूल्यवान फ़ीडबैक और समय देने के लिए धन्यवाद। आपका दिन शुभ हो।",
        "type": "closing"
    }
]

