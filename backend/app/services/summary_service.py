"""Service for generating summaries and closing statements"""

from  llm.gemini_client import model
import logging
import json
import re

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
        logger.info("=" * 80)
        logger.info("🤖 LLM CALL (transliterate_to_devanagari) - Input:")
        logger.info(f"Name: {name}")
        logger.info("-" * 80)

        response = model.generate_content(prompt)

        if response and response.text:
            result = response.text.strip()
            # Strip special tokens that GPT-OSS models sometimes include
            result = re.sub(r'<\|[^|]+\|>', '', result)  # Remove <|token|> patterns
            result = re.sub(r'<return>', '', result, flags=re.IGNORECASE)
            result = result.strip()
            logger.info("📥 LLM CALL (transliterate_to_devanagari) - Raw Response:")
            logger.info(response.text)
            logger.info("-" * 80)
            logger.info(f"✅ LLM CALL (transliterate_to_devanagari) - Result: {result}")
            logger.info("=" * 80)
            return result

        logger.warning(
            "⚠️ LLM CALL (transliterate_to_devanagari) - Empty response, returning original name"
        )
        logger.info("=" * 80)
        return name
    except Exception as e:
        logger.error(
            f"❌ LLM CALL (transliterate_to_devanagari) - Error: {e}", exc_info=True
        )
        logger.info("=" * 80)
        return name


def generate_human_summary(session: dict) -> str:
    """Generate a human-readable summary from session data using LLM"""
    # Filter out internal fields
    summary_data = {
        k: v
        for k, v in session.items()
        if v is not None
        and k
        not in [
            "session_id",
            "current_question",
            "retry_count",
            "call_should_end",
            "phase",
            "generated_summary",
            "summary_confirmed",
            "acknowledgment_text",
            "customer_name_english",
            "identify_confirmation",
        ]
    }

    # FIX 3: Improved prompt with clear structure for payee, executive, reason, date
    prompt = f"""
        आप एक कस्टमर सर्विस प्रतिनिधि हैं और ग्राहक से फ़ोन पर स्वाभाविक बातचीत कर रहे हैं।
        नीचे दिए गए वार्तालाप डेटा के आधार पर हिंदी (केवल देवनागरी लिपि में) एक सरल, बोलचाल की पुष्टि-वाली पंक्ति तैयार करें।

        {json.dumps(summary_data, indent=2, ensure_ascii=False)}

        महत्वपूर्ण निर्देश:
        1. उत्तर ऐसा हो जैसे आप कॉल पर ग्राहक से विवरण की पुष्टि कर रहे हों।
        2. भाषा स्वाभाविक हिंदी / आम बोलचाल वाली हो, लेकिन रोमन लिपि का प्रयोग बिल्कुल न करें।
        3. पूरा उत्तर केवल देवनागरी लिपि में हो; कोई भी अंग्रेज़ी या रोमन शब्द न हों।
        4. भुगतान से जुड़ी जानकारी हमेशा इसी क्रम में रखें:
        (क) किसने भुगतान किया (यदि ग्राहक ने स्वयं किया हो तो वही दर्शाएँ)
        (ख) राशि
        (ग) भुगतान का कारण (जैसे ईएमआई, सेटलमेंट, फोरक्लोज़र आदि)
        (घ) भुगतान की तारीख
        (ङ) भुगतान का माध्यम (ऑनलाइन, नकद, शाखा, एनएसीएच आदि — देवनागरी में)
        (च) किसे भुगतान किया गया (यदि फ़ील्ड एग्ज़ीक्यूटिव का नाम उपलब्ध हो तो)

        वाक्य संरचना के उदाहरण:
        - यदि ग्राहक ने स्वयं भुगतान किया हो:
        "आपने [राशि] रुपये का भुगतान [कारण] के लिए [तारीख] को किया था और यह [भुगतान माध्यम] से किया गया था।"

        - यदि किसी अन्य व्यक्ति ने भुगतान किया हो:
        "[भुगतानकर्ता] ने [राशि] रुपये का भुगतान [कारण] के लिए [तारीख] को किया था और यह [भुगतान माध्यम] से किया गया था।"

        - यदि फ़ील्ड एग्ज़ीक्यूटिव को भुगतान किया गया हो:
        "आपने [राशि] रुपये [एक्ज़ीक्यूटिव का नाम] को [कारण] के लिए [तारीख] को दिए थे और यह [भुगतान माध्यम] से किया गया था।"

        5. विवरण बताने के बाद अंत में यह प्रश्न अवश्य पूछें:
        "क्या यह जानकारी सही है?"

        6. अभिवादन, बुलेट पॉइंट, शीर्षक या “सारांश” जैसे शब्द न जोड़ें।
        7. विराम-चिह्नों का सही प्रयोग करें—अल्पविराम, पूर्णविराम और प्रश्नवाचक चिन्ह।

        उदाहरण आउटपुट:
        "आपने 5000 रुपये का भुगतान अपनी ईएमआई के लिए 15 दिसंबर को किया था और यह ऑनलाइन माध्यम से किया गया था। क्या यह जानकारी सही है?"

        अब उपरोक्त निर्देशों के अनुसार उत्तर तैयार करें।
    """

    try:
        logger.info("=" * 80)
        logger.info("🤖 LLM CALL (generate_human_summary) - Input Session Data:")
        logger.info("-" * 80)
        logger.info(json.dumps(summary_data, indent=2, ensure_ascii=False))
        logger.info("-" * 80)

        response = model.generate_content(prompt)

        if response and response.text:
            result = response.text.strip()
            # Strip special tokens that GPT-OSS models sometimes include
            result = re.sub(r'<\|[^|]+\|>', '', result)  # Remove <|token|> patterns
            result = re.sub(r'<return>', '', result, flags=re.IGNORECASE)
            result = result.strip()
            logger.info("📥 LLM CALL (generate_human_summary) - Raw Response:")
            logger.info(response.text)
            logger.info("-" * 80)
            logger.info(f"✅ LLM CALL (generate_human_summary) - Generated Summary:")
            logger.info(result)
            logger.info("=" * 80)
            return result
        else:
            logger.warning(
                "⚠️ LLM CALL (generate_human_summary) - Empty response, using fallback summary"
            )
            logger.info("=" * 80)
            # Fallback to basic summary if LLM fails
            return generate_fallback_summary(summary_data)
    except Exception as e:
        logger.error(
            f"❌ LLM CALL (generate_human_summary) - Error: {e}", exc_info=True
        )
        logger.info("=" * 80)
        return generate_fallback_summary(summary_data)


def generate_fallback_summary(data: dict) -> str:
    """Generate a basic conversational summary if LLM fails"""
    summary_parts = []

    # WHO paid
    payee = data.get("payee", "self")
    payee_text = "आपने" if payee == "self" else f"{data.get('payee_name', 'किसी ने')}"

    # AMOUNT
    amount = data.get("amount", "")

    # WHY (reason)
    reason = data.get("reason", "")
    reason_map = {
        "emi": "ईएमआई",
        "emi_charges": "ईएमआई चार्जेज",
        "settlement": "सेटलमेंट",
        "foreclosure": "फोरक्लोजर",
        "charges": "चार्जेज",
        "loan_cancellation": "लोन कैंसिलेशन",
        "advance_emi": "एडवांस ईएमआई",
    }
    reason_text = reason_map.get(reason, reason) if reason else "भुगतान"

    # WHEN (date)
    pay_date = data.get("pay_date", "")

    # HOW (payment mode)
    mode = data.get("mode_of_payment", "")
    mode_map = {
        "online": "ऑनलाइन",
        "online_lan": "ऑनलाइन",
        "online_field_executive": "ऑनलाइन फील्ड एग्जीक्यूटिव",
        "cash": "नगद",
        "branch": "ब्रांच",
        "outlet": "आउटलेट",
        "nach": "ऑटो डेबिट (NACH)",
    }
    mode_text = mode_map.get(mode, mode) if mode else ""

    # TO WHOM (executive)
    executive = data.get("field_executive_name", "")

    # Build the summary
    if executive:
        # If executive is mentioned
        summary = f"{payee_text} ₹{amount} रुपये {executive} को {reason_text} के लिए"
        if pay_date:
            summary += f" {pay_date} को"
        summary += " दिए थे"
        if mode_text:
            summary += f" और यह {mode_text} से किया था"
    else:
        # No executive
        summary = f"{payee_text} ₹{amount} रुपये का भुगतान {reason_text} के लिए"
        if pay_date:
            summary += f" {pay_date} को"
        summary += " किया था"
        if mode_text:
            summary += f" और यह {mode_text} माध्यम से किया है"

    summary += "। क्या यह जानकारी सही है?"

    return summary


def is_survey_completed(session: dict) -> bool:
    """Check if survey is completed without modifying the session"""
    # Lazy import to avoid circular dependency
    from  flow.flow_manager import get_next_question_index
    from  flow.question_order import QUESTIONS

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
        logger.info("=" * 80)
        logger.info("🤖 LLM CALL (detect_confirmation) - Input:")
        logger.info(f"User response: {user_input}")
        logger.info("-" * 80)

        response = model.generate_content(prompt)

        if response and response.text:
            result = response.text.strip().upper()
            logger.info("📥 LLM CALL (detect_confirmation) - Raw Response:")
            logger.info(response.text)
            logger.info("-" * 80)

            if "YES" in result:
                logger.info("✅ LLM CALL (detect_confirmation) - Result: YES")
                logger.info("=" * 80)
                return "YES"
            elif "NO" in result:
                logger.info("✅ LLM CALL (detect_confirmation) - Result: NO")
                logger.info("=" * 80)
                return "NO"

        logger.warning("⚠️ LLM CALL (detect_confirmation) - Result: UNCLEAR")
        logger.info("=" * 80)
        return "UNCLEAR"
    except Exception as e:
        logger.error(f"❌ LLM CALL (detect_confirmation) - Error: {e}", exc_info=True)
        logger.info("=" * 80)
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
    - Payee (भुगतान करता): {session.get('payee')}
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
        logger.info("=" * 80)
        logger.info("🤖 LLM CALL (detect_field_to_edit) - Input:")
        logger.info(f"User response: {user_input}")
        logger.info("Current session data:")
        logger.info(
            json.dumps(
                {
                    "amount": session.get("amount"),
                    "pay_date": session.get("pay_date"),
                    "mode_of_payment": session.get("mode_of_payment"),
                    "payee": session.get("payee"),
                    "reason": session.get("reason"),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        logger.info("-" * 80)

        response = model.generate_content(prompt)

        if response and response.text:
            logger.info("📥 LLM CALL (detect_field_to_edit) - Raw Response:")
            logger.info(response.text)
            logger.info("-" * 80)

            lines = response.text.strip().split("\n")
            field = None
            value = None
            for line in lines:
                if line.startswith("FIELD:"):
                    field = line.replace("FIELD:", "").strip().lower()
                elif line.startswith("VALUE:"):
                    value = line.replace("VALUE:", "").strip()

            if field and field != "none" and value and value.lower() != "none":
                result = {"field": field, "value": value}
                logger.info(
                    f"✅ LLM CALL (detect_field_to_edit) - Result: {json.dumps(result, indent=2, ensure_ascii=False)}"
                )
                logger.info("=" * 80)
                return result

        logger.warning(
            "⚠️ LLM CALL (detect_field_to_edit) - Could not detect field, returning None"
        )
        logger.info("=" * 80)
        return None
    except Exception as e:
        logger.error(f"❌ LLM CALL (detect_field_to_edit) - Error: {e}", exc_info=True)
        logger.info("=" * 80)
        return None


def get_edit_prompt() -> str:
    """Get the prompt asking which field to edit"""
    return "कौन सी जानकारी बदलनी है? कृपया बताइए।"


def get_closing_statement(session: dict) -> str:
    """Generate closing statement based on session data"""
    call_end_reason = session.get("call_end_reason")
    
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
        elif session.get("last_month_emi_payment") == "NO":
            return (
                "धन्यवाद आपके समय के लिए।\n"
                "आपकी फीडबैक हमारे लिए बहुत महत्वपूर्ण है।\n"
                "आपका दिन शुभ हो!"
            )
    else:
        return (
            "आपके मूल्यवान फ़ीडबैक और समय देने के लिए धन्यवाद।\n"
            "आपका दिन शुभ हो।"
        )
