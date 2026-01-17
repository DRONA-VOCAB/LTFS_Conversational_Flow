"""Service for generating summaries and closing statements"""

from ..llm.gemini_client import model
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
    # Use conversational fields if available, otherwise fall back to legacy fields
    summary_data = {}
    
    # Map conversational fields to summary data
    if session.get("identity_confirmed"):
        summary_data["identity_confirmed"] = session.get("identity_confirmed")
    elif session.get("identify_confirmation"):
        summary_data["identity_confirmed"] = session.get("identify_confirmation")
    
    if session.get("loan_taken"):
        summary_data["loan_taken"] = session.get("loan_taken")
    
    if session.get("last_month_payment"):
        summary_data["last_month_payment"] = session.get("last_month_payment")
    elif session.get("last_month_emi_payment"):
        summary_data["last_month_payment"] = session.get("last_month_emi_payment")
    
    if session.get("payee"):
        summary_data["payee"] = session.get("payee")
    
    if session.get("payment_date"):
        summary_data["payment_date"] = session.get("payment_date")
    elif session.get("pay_date"):
        summary_data["payment_date"] = session.get("pay_date")
    
    if session.get("payment_mode"):
        summary_data["payment_mode"] = session.get("payment_mode")
    elif session.get("mode_of_payment"):
        summary_data["payment_mode"] = session.get("mode_of_payment")
    
    if session.get("payment_reason"):
        summary_data["payment_reason"] = session.get("payment_reason")
    elif session.get("reason"):
        summary_data["payment_reason"] = session.get("reason")
    
    if session.get("payment_amount"):
        summary_data["payment_amount"] = session.get("payment_amount")
    elif session.get("amount"):
        summary_data["payment_amount"] = session.get("amount")

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

    # Build natural conversational summary using new field names
    amount = data.get("payment_amount") or data.get("amount")
    mode = data.get("payment_mode") or data.get("mode_of_payment")
    
    if amount and mode:
        # Convert mode to readable format
        mode_map = {
            "online_lan": "online",
            "online": "online",
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
    elif amount:
        summary_parts.append(f" ₹{amount} ka payment kiya tha")
    elif data.get("last_month_payment") == "YES" or data.get("last_month_emi_payment") == "YES":
        summary_parts.append("pichle mahine EMI payment Hua tha.")

    pay_date = data.get("payment_date") or data.get("pay_date")
    if pay_date:
        summary_parts.append(f"payment {pay_date} date ko ki gai thi.")

    if not summary_parts:
        # Fallback if no key data
        summary_parts.append(
            "Aapne L&T Finance se loan liya hai aur aapne payment kiya hai."
        )

    return " ".join(summary_parts)


def is_survey_completed(session: dict) -> bool:
    """Check if survey is completed without modifying the session"""
    # Lazy import to avoid circular dependency
    from ..flow.flow_manager import get_next_question_index
    from ..flow.question_order import QUESTIONS

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
    call_end_reason = session.get("call_end_reason")
    
    if session.get("call_should_end"):
        # Check specific end reasons from conversational flow
        if call_end_reason == "no_loan" or session.get("loan_taken") == "NO":
            return "धन्यवाद आपके समय के लिए। आपका दिन शुभ हो!"
        elif call_end_reason == "wrong_person" or session.get("identity_confirmed") == "NO":
            if session.get("user_contact"):
                return (
                    "धन्यवाद आपके समय के लिए।\n"
                    "हम आपके द्वारा बताए गए समय पर उनसे संपर्क करेंगे।\n"
                    "आपका दिन शुभ हो!"
                )
            else:
                return (
                    "धन्यवाद आपके समय के लिए।\n"
                    "हम आपके द्वारा बताए गए समय पर ग्राहक से संपर्क करेंगे।\n"
                    "आपका दिन शुभ हो!"
                )
        # Check legacy fields for backward compatibility
        elif session.get("identify_confirmation") == "NO":
            if session.get("user_contact"):
                return (
                    "धन्यवाद आपके समय के लिए।\n"
                    "हम आपके द्वारा बताए गए समय पर उनसे संपर्क करेंगे।\n"
                    "आपका दिन शुभ हो!"
                )
            else:
                return (
                    "धन्यवाद आपके समय के लिए।\n"
                    "हम आपके द्वारा बताए गए समय पर ग्राहक से संपर्क करेंगे।\n"
                    "आपका दिन शुभ हो!"
                )
        else:
            return "धन्यवाद आपके समय के लिए। आपका दिन शुभ हो!"
    else:
        return (
            "आपके मूल्यवान फ़ीडबैक और समय देने के लिए धन्यवाद।\n"
            "आपका दिन शुभ हो।"
        )
