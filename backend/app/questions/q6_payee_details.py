from  base import QuestionResult
from  llm.gemini_client import call_gemini


def get_text():
    return "कृपया बताइए, इस अकाउंट का भुगतान किसने किया है? क्या मैं भुगतानकर्ता का नाम और संपर्क नंबर नोट कर सकती हूँ?"


PROMPT ="""
        You are an intelligent assistant.

        Question asked to the user:
        "कृपया बताइए, इस अकाउंट का भुगतान किसने किया है? क्या मैं भुगतानकर्ता का नाम और संपर्क नंबर नोट कर सकती हूँ?"

        Your task is to extract the NAME of the person who made the payment and their CONTACT NUMBER
        (if mentioned) from the user's response.

        ========================
        EXTRACTION TARGETS
        ========================

        1. payee_name:
        - Name or relation of the person who made the payment
        - Can be a proper name or a relationship (father, mother, friend, agent, etc.)

        2. payee_contact:
        - Any phone number mentioned
        - Extract digits as-is (even if incomplete)
        - Ignore spaces, dashes, or country codes if present

        ========================
        EXAMPLES (DEVANAGARI FIRST)
        ========================

        "मेरे पापा रमेश ने किया था, नंबर 9876543210 है"
        → payee_name: "पापा रमेश"
        → payee_contact: "9876543210"

        "भुगतान मेरी मम्मी ने किया, उनका नंबर 9123456789 है"
        → payee_name: "मम्मी"
        → payee_contact: "9123456789"

        "राहुल ने किया था"
        → payee_name: "राहुल"
        → payee_contact: null

        "किसी और ने किया था, नंबर 9998887777"
        → payee_name: "किसी और"
        → payee_contact: "9998887777"

        "मुझे नाम याद नहीं है, पर नंबर 9876501234 है"
        → payee_name: null
        → payee_contact: "9876501234"


        Roman examples:
        "mere papa Ramesh ne kiya tha number 9876543210"
        → payee_name: "papa Ramesh"
        → payee_contact: "9876543210"

        "payment mummy ne kiya"
        → payee_name: "mummy"
        → payee_contact: null

        "Rahul ne kiya"
        → payee_name: "Rahul"
        → payee_contact: null

        "kisi aur ne kiya number 9998887777"
        → payee_name: "kisi aur"
        → payee_contact: "9998887777"


        ========================
        UNCLEAR CASES
        ========================

        If the response:
        - Does not mention name or contact number
        - Is ambiguous or unrelated
        - Only repeats the question
        - Is noise / silence

        Examples:
        "पता नहीं",
        "याद नहीं है",
        "मालूम नहीं",
        unrelated responses

        → Set both values to null and is_clear = false

        ========================
        IMPORTANT INSTRUCTIONS
        ========================

        - Extract ONLY what is clearly stated
        - Do NOT guess missing names or numbers
        - If an item is not mentioned, set it to null
        - If at least one of payee_name or payee_contact is extracted, set is_clear = true
        - Do NOT explain your reasoning
        - Do NOT add extra fields
        - Return ONLY valid JSON (no markdown, no text outside JSON)

        ========================
        OUTPUT FORMAT (STRICT)
        ========================

        {
        "value": {
            "payee_name": "name or null",
            "payee_contact": "phone number or null"
        },
        "is_clear": true/false
        }
    """


def handle(user_input, session):
    r = call_gemini(PROMPT + user_input)
    if not r["is_clear"]:
        return QuestionResult(False)
    session["payee_name"] = r["value"].get("payee_name")
    session["payee_contact"] = r["value"].get("payee_contact")
    return QuestionResult(True)

