from base import QuestionResult
from  llm.gemini_client import call_gemini


def get_text():
    customer_name = "{{customer_name}}"
    return f"कृपया बताइए कि {customer_name} जी से किस समय बात करना ठीक रहेगा? अगर कोई दूसरा नंबर हो तो वह भी बता दीजिए।"


PROMPT = """
        You are an intelligent assistant. Your task is to extract availability information and an alternate contact number
        from the user's response.

        ========================
        EXTRACTION TARGETS
        ========================

        1. preferred_time:
        - Extract ANY time or availability reference if mentioned.
        - Examples include:
            - Explicit times: "5 बजे", "5 bje", "5pm", "5 pm", "17:00"
            - Time ranges: "शाम को", "सुबह", "दोपहर", "रात", "evening", "morning"
            - Immediate availability: "अभी", "अभी कॉल करें", "अब", "now", "right now", "immediately"
            - Implied availability without time:
            - "इसी नंबर पर कॉल कर देना"
            - "यहीं बात हो जाएगी"
            - "अभी बात कर सकते हैं"
            → In such cases, set preferred_time as "now"

        2. alternate_contact:
        - Extract ANY phone number if present.
        - Accept:
            - Pure digits: "123456789", "9876543210"
            - Numbers spoken with context: "ये उनका नंबर है 9876543210"
            - Short or incomplete numbers should still be extracted as-is.
        - Ignore formatting symbols like spaces, dashes, or country codes if present.

        ========================
        EXAMPLES (DEVANAGARI FIRST)
        ========================

        "123456789 ये उनका नंबर है"
        → alternate_contact: "123456789"

        "उनका नंबर 9876543210 है"
        → alternate_contact: "9876543210"

        "वो 5 बजे उपलब्ध होंगी"
        → preferred_time: "5 बजे"

        "शाम को कॉल कर लेना"
        → preferred_time: "शाम"

        "अभी फोन कर लीजिए"
        → preferred_time: "now"

        "इसी नंबर पर कॉल कर देना"
        → preferred_time: "now"

        "कल सुबह बात कर सकते हैं"
        → preferred_time: "सुबह"

        "9876543210 पर शाम को कॉल करना"
        → alternate_contact: "9876543210"
        → preferred_time: "शाम"

        ========================
        IMPORTANT INSTRUCTIONS
        ========================

        - Extract only what is explicitly or clearly implied
        - If an item is not mentioned, set it to null
        - If at least one of preferred_time or alternate_contact is extracted, set is_clear = true
        - If nothing relevant is found, set both values to null and is_clear = false
        - Do NOT guess missing information
        - Do NOT explain your reasoning
        - Do NOT add extra fields
        - Return ONLY valid JSON (no markdown, no text outside JSON)

        ========================
        OUTPUT FORMAT (STRICT)
        ========================

        {
        "value": {
            "preferred_time": "time mentioned or null",
            "alternate_contact": "phone number or null"
        },
        "is_clear": true/false
        }
    """



def handle(user_input, session):
    r = call_gemini(PROMPT + user_input)
    if not r["is_clear"]:
        return QuestionResult(False)
    session["availability"] = r["value"].get("preferred_time")
    session["user_contact"] = r["value"].get("alternate_contact")

    # If identity is NO and either alternate contact or availability/time is provided, end the call
    if session.get("identify_confirmation") == "NO":
        if session["user_contact"] or session["availability"]:
            session["call_should_end"] = True

    return QuestionResult(True)
