"""Service for generating summaries and closing statements"""

from llm.gemini_client import model
import logging

logger = logging.getLogger(__name__)


def transliterate_to_devanagari(name: str) -> str:
    """Convert English name to Devanagari script using LLM"""
    if not name:
        return name

    prompt = f"""Convert the following English name to Devanagari (Hindi) script.
    Only return the converted name, nothing else.
    
    Name: {name}
    
    Devanagari:"""

    try:
        response = model.generate_content(prompt)
        if response and response.text:
            return response.text.strip()
        return name
    except Exception as e:
        logger.error(f"Error transliterating name: {e}")
        return name


def generate_human_summary(session: dict) -> str:
    """Generate a human-readable summary from session data using LLM"""
    # Filter out internal fields
    summary_data = {
        k: v
        for k, v in session.items()
        if v is not None
        and k
        not in ["session_id", "current_question", "retry_count", "call_should_end"]
    }

    # Create a prompt for generating human-readable summary
    prompt = f"""You are a customer service representative having a natural conversation with a customer. 
        Generate a simple, conversational summary in Hindi/Hinglish based on the following conversation data:

        {summary_data}

        Create a natural, human-like summary as if you're speaking directly to the customer:
        1. Keep it short and simple - like you're talking on a phone call
        2. Use natural Hindi/Hinglish - mix of Hindi and English as people speak
        3. Focus on key payment details: amount, payment method, date
        4. Write it as a single flowing sentence or two, not a formal list
        5. Example format: "आपने 3000 रुपये का भुगतान अपनी ईएमआई के लिए किया था और यह आपने ऑनलाइन माध्यम से किया है। क्या यह जानकारी सही है?"

        Do NOT include:
        - Formal greetings like "Namaste" or "Aapke survey ke anusaar"
        - Bullet points or lists
        - Long explanations
        - "Summary" or "conversation" words

        Just write the key information naturally as if speaking but give in devnagri script not in roman:
    """

    try:
        response = model.generate_content(prompt)
        if response and response.text:
            return response.text.strip()
        else:
            # Fallback to basic summary if LLM fails
            return generate_fallback_summary(summary_data)
    except Exception as e:
        print(f"Error generating summary: {e}")
        return generate_fallback_summary(summary_data)


def generate_fallback_summary(data: dict) -> str:
    """Generate a basic conversational summary if LLM fails"""
    summary_parts = []

    # Build natural conversational summary
    if data.get("amount") and data.get("mode_of_payment"):
        amount = data.get("amount")
        mode = data.get("mode_of_payment")
        # Convert mode to readable format
        mode_map = {
            "online": "online",
            "online_lan": "online",
            "online_field_executive": "online field executive",
            "cash": "cash",
            "branch": "branch",
            "outlet": "outlet",
            "nach": "NACH",
        }
        mode_text = mode_map.get(mode, mode)
        summary_parts.append(
            f" ₹{amount} ka payment kiya tha aur ye payment {mode_text} madhyam se kiya hai."
        )
    elif data.get("amount"):
        summary_parts.append(f" ₹{data.get('amount')} ka payment kiya tha")
    elif data.get("last_month_emi_payment") == "YES":
        summary_parts.append("pichle mahine EMI payment Hua tha.")

    if data.get("pay_date"):
        summary_parts.append(f"payment {data.get('pay_date')} date ko ki gai thi.")

    if not summary_parts:
        # Fallback if no key data
        summary_parts.append(
            "Aapne L&T Finance se loan liya hai aur aapne payment kiya hai."
        )

    return " ".join(summary_parts)


def is_survey_completed(session: dict) -> bool:
    """Check if survey is completed without modifying the session"""
    # Lazy import to avoid circular dependency
    from flow.flow_manager import get_next_question_index
    from flow.question_order import QUESTIONS

    next_idx = get_next_question_index(session)
    return next_idx >= len(QUESTIONS) or session.get("call_should_end", False)


def detect_confirmation(user_input: str) -> str:
    """Use LLM to detect if user confirmed or denied the summary
    Returns: 'YES', 'NO', or 'UNCLEAR'
    """
    prompt = f"""Analyze the following user response to determine if they are confirming or denying.
    The user was asked: "क्या यह जानकारी सही है?" (Is this information correct?)
    
    User response: "{user_input}"
    
    Return ONLY one of these three options:
    - YES (if user confirms, agrees, says correct, sahi hai, theek hai, haan, etc.)
    - NO (if user denies, disagrees, says wrong, galat, nahi, change karna hai, etc.)
    - UNCLEAR (if the response is ambiguous or unrelated)
    
    Response:"""

    try:
        response = model.generate_content(prompt)
        if response and response.text:
            result = response.text.strip().upper()
            if "YES" in result:
                return "YES"
            elif "NO" in result:
                return "NO"
        return "UNCLEAR"
    except Exception as e:
        logger.error(f"Error detecting confirmation: {e}")
        return "UNCLEAR"


def detect_field_to_edit(user_input: str, session: dict) -> dict:
    """Use LLM to detect which field the user wants to edit and the new value
    Returns: {"field": field_name, "value": new_value} or None
    """
    # Map of editable fields with their Hindi descriptions
    field_map = {
        "amount": "राशि/अमाउंट",
        "pay_date": "भुगतान की तारीख/डेट",
        "mode_of_payment": "भुगतान का माध्यम/मोड",
        "payee": "किसने भुगतान किया",
        "reason": "भुगतान का कारण",
    }

    prompt = f"""Analyze the user's response to determine which field they want to edit and what the new value should be.
    
    Current session data:
    - Amount (राशि): {session.get('amount')}
    - Payment Date (तारीख): {session.get('pay_date')}
    - Payment Mode (माध्यम): {session.get('mode_of_payment')}
    - Payee (भुगतान कर्ता): {session.get('payee')}
    - Reason (कारण): {session.get('reason')}
    
    User said: "{user_input}"
    
    Return in this exact format (just the field name and value, nothing else):
    FIELD: <field_name>
    VALUE: <new_value>
    
    Field names must be one of: amount, pay_date, mode_of_payment, payee, reason
    If you cannot determine which field to edit, return:
    FIELD: NONE
    VALUE: NONE
    
    Response:"""

    try:
        response = model.generate_content(prompt)
        if response and response.text:
            lines = response.text.strip().split("\n")
            field = None
            value = None
            for line in lines:
                if line.startswith("FIELD:"):
                    field = line.replace("FIELD:", "").strip().lower()
                elif line.startswith("VALUE:"):
                    value = line.replace("VALUE:", "").strip()

            if field and field != "none" and value and value.lower() != "none":
                return {"field": field, "value": value}
        return None
    except Exception as e:
        logger.error(f"Error detecting field to edit: {e}")
        return None


def get_edit_prompt() -> str:
    """Get the prompt asking which field to edit"""
    return "कौन सी जानकारी बदलनी है? कृपया बताइए।"


def get_closing_statement(session: dict) -> str:
    """Generate closing statement based on session data"""
    if session.get("call_should_end"):
        # Check if it's a wrong number case (loan_taken is NO)
        if session.get("loan_taken") == "NO":
            return "धन्यवाद आपके समय के लिए।\nआपका दिन शुभ हो!"
        # Check if alternate number was provided
        elif session.get("user_contact"):
            return (
                "धन्यवाद आपके समय के लिए।\n"
                "हम आपके द्वारा बताए गए समय पर उनसे संपर्क करेंगे।\n"
                "आपका दिन शुभ हो!"
            )
        # Otherwise, it's availability case without alternate number
        else:
            return (
                "धन्यवाद आपके समय के लिए।\n"
                "हम आपके द्वारा बताए गए समय पर ग्राहक से संपर्क करेंगे।\n"
                "आपका दिन शुभ हो!"
            )
    else:
        return (
            "धन्यवाद आपके समय के लिए।\n"
            "आपकी फीडबैक हमारे लिए बहुत महत्वपूर्ण है।\n"
            "आपका दिन शुभ हो!"
        )
