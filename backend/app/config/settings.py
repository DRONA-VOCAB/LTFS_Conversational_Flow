import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration
GEMINI_MODEL = os.getenv("GEMINI_MODEL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Company/Brand Configuration
COMPANY_NAME = os.getenv("COMPANY_NAME", "L and T finance")
COMPANY_NAME_FORMAL = os.getenv("COMPANY_NAME_FORMAL", "L&T Finance")
COMPANY_NAME_SHORT = os.getenv("COMPANY_NAME_SHORT", "L&T")

# API Configuration
API_TITLE = os.getenv("API_TITLE", f"{COMPANY_NAME_FORMAL} Customer Survey API")
API_DESCRIPTION = os.getenv("API_DESCRIPTION", "API for managing customer survey sessions")
API_VERSION = os.getenv("API_VERSION", "1.0.0")

# Message Templates
MESSAGES = {
    # Greeting/Introduction
    "greeting": os.getenv(
        "MESSAGE_GREETING",
        "नमस्ते, मैं {company_name} की तरफ़ से बात कर रही हूँ, क्या मेरी बात {{customer_name}} जी से हो रही है?"
    ),
    
    # Role Clarification
    "role_clarification": os.getenv(
        "MESSAGE_ROLE_CLARIFICATION",
        "जी हाँ, मैं {company_name} की तरफ़ से बात कर रही हूँ। मैं एक AI assistant हूँ जो आपके भुगतान अनुभव के बारे में कुछ जानकारी लेने के लिए कॉल कर रही हूँ। क्या मेरी बात {{customer_name}} जी से हो रही है?"
    ),
    
    # Name Correction Acknowledgment
    "name_corrected_with_name": os.getenv(
        "MESSAGE_NAME_CORRECTED_WITH_NAME",
        "धन्यवाद, मैंने नाम {corrected_name} जी के रूप में अपडेट कर दिया है। क्या मेरी बात {corrected_name} जी से हो रही है?"
    ),
    "name_corrected_generic": os.getenv(
        "MESSAGE_NAME_CORRECTED_GENERIC",
        "धन्यवाद, मैंने नाम अपडेट कर दिया है। क्या मेरी बात {{customer_name}} जी से हो रही है?"
    ),
    
    # Not Available Response
    "not_available": os.getenv(
        "MESSAGE_NOT_AVAILABLE",
        "मैं समझ गई। कृपया बताइए कि {{customer_name}} जी कब उपलब्ध होंगे? या फिर मैं आपको कॉल का उद्देश्य बता सकती हूँ।"
    ),
    
    # Sensitive Situation
    "sensitive_situation": os.getenv(
        "MESSAGE_SENSITIVE_SITUATION",
        "मुझे बहुत दुख है। मैं आपके और आपके परिवार के प्रति अपनी संवेदना व्यक्त करती हूँ। धन्यवाद आपके समय के लिए।"
    ),
    
    # Wrong Number / No Loan
    "wrong_number_apology": os.getenv(
        "MESSAGE_WRONG_NUMBER",
        "माफ़ कीजिए, गलत नंबर पर कॉल कर दी। धन्यवाद आपके समय के लिए। आपका दिन शुभ हो!"
    ),
    
    # Availability - Contact Provided
    "availability_contact_provided": os.getenv(
        "MESSAGE_AVAILABILITY_CONTACT_PROVIDED",
        "धन्यवाद आपके समय के लिए। हम आपके द्वारा बताए गए समय पर ग्राहक से संपर्क करेंगे। आपका दिन शुभ हो!"
    ),
    
    # Confused About Customer
    "confused_about_customer": os.getenv(
        "MESSAGE_CONFUSED_ABOUT_CUSTOMER",
        "धन्यवाद आपके समय के लिए। हम इस जानकारी को नोट कर लेंगे। आपका दिन शुभ हो!"
    ),
    
    # Closing Messages
    "closing_wrong_number": os.getenv(
        "MESSAGE_CLOSING_WRONG_NUMBER",
        "धन्यवाद आपके समय के लिए।\nआपका दिन शुभ हो!"
    ),
    "closing_alternate_contact": os.getenv(
        "MESSAGE_CLOSING_ALTERNATE_CONTACT",
        "धन्यवाद आपके समय के लिए।\nहम आपके द्वारा बताए गए समय पर उनसे संपर्क करेंगे।\nआपका दिन शुभ हो!"
    ),
    "closing_availability": os.getenv(
        "MESSAGE_CLOSING_AVAILABILITY",
        "धन्यवाद आपके समय के लिए।\nहम आपके द्वारा बताए गए समय पर ग्राहक से संपर्क करेंगे।\nआपका दिन शुभ हो!"
    ),
    "closing_success": os.getenv(
        "MESSAGE_CLOSING_SUCCESS",
        "धन्यवाद आपके समय के लिए।\nआपकी फीडबैक हमारे लिए बहुत महत्वपूर्ण है।\nआपका दिन शुभ हो!"
    ),
}

# Payment Mode Mappings (for summary generation)
PAYMENT_MODE_MAP = {
    "online": "online",
    "online_lan": "online",
    "online_field_executive": "online field executive",
    "cash": "cash",
    "branch": "branch",
    "outlet": "outlet",
    "nach": "NACH",
}

# Fallback Summary Template
FALLBACK_SUMMARY_TEMPLATE = os.getenv(
    "FALLBACK_SUMMARY_TEMPLATE",
    "Aapne {company_name} se loan liya hai aur aapne payment kiya hai."
)


def get_message(key: str, **kwargs) -> str:
    """Get a message template and format it with provided kwargs"""
    message = MESSAGES.get(key, "")
    # Replace company_name placeholder
    message = message.replace("{company_name}", COMPANY_NAME)
    # Replace any other kwargs
    if kwargs:
        message = message.format(**kwargs)
    return message
