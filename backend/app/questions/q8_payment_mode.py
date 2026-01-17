from .base import QuestionResult
from ..llm.gemini_client import call_gemini


def get_text():
    return "भुगतान किस माध्यम से किया गया था? क्या आपने ऑनलाइन, यूपीआई या नगद दिया था?"


PROMPT = """
        You are an intelligent assistant.

        Question asked to the user:
        "भुगतान (पेमेंट) किस माध्यम से किया गया था?"

        Your task is to extract the PAYMENT MODE from the user's response.

        ========================
        AVAILABLE PAYMENT MODES
        ========================

        1. online_lan
        - Online payments made directly by the customer

        2. online_field_executive
        - Online payment done through a field executive

        3. cash
        - Cash / cash-in-hand payment

        4. branch
        - Payment done at bank / company branch

        5. outlet
        - Payment done at an outlet

        6. nach
        - Automated / auto-debit / NACH payments

        ========================
        MAPPING RULES
        ========================

        Map the user's response to ONE of the following modes:

        online_lan →
        "ऑनलाइन", "ऑनलाइन किया", "ऑनलाइन से", "ऑनलाइन माध्यम से",
        "यूपीआई", "यु पी आई", "नेट बैंकिंग", "इंटरनेट बैंकिंग",
        "फोन से किया", "गूगल पे", "फोनपे", "पेटीएम"

        online_field_executive →
        "फील्ड एग्जीक्यूटिव को दिया",
        "एग्जीक्यूटिव के माध्यम से",
        "फील्ड एग्जीक्यूटिव से",
        "एग्जीक्यूटिव ने ऑनलाइन किया"

        cash →
        "कैश", "नगद", "नकद",
        "कैश दिया", "नगद भुगतान", "हाथ से दिया"

        branch →
        "ब्रांच में किया",
        "शाखा में किया",
        "बैंक में किया",
        "ब्रांच जाकर किया"

        outlet →
        "आउटलेट में किया",
        "आउटलेट जाकर किया"

        nach →
        "नाच", "नैच",
        "ऑटो डेबिट",
        "ऑटोमैटिक कटता है",
        "अपने आप कट जाता है",
        "NACH", "auto debit"


        ========================
        EXAMPLES (DEVANAGARI FIRST)
        ========================

        "मैंने ऑनलाइन किया था"
        → mode: "online_lan"

        "यूपीआई से किया"
        → mode: "online_lan"

        "फील्ड एग्जीक्यूटिव को ऑनलाइन दिया था"
        → mode: "online_field_executive"

        "कैश दिया था"
        → mode: "cash"

        "ब्रांच में जाकर पेमेंट किया"
        → mode: "branch"

        "आउटलेट में किया था"
        → mode: "outlet"

        "ऑटो डेबिट से कटता है"
        → mode: "nach"


        Roman examples:
        "online kiya tha"
        → mode: "online_lan"

        "upi se payment ki"
        → mode: "online_lan"

        "field executive ko diya tha"
        → mode: "online_field_executive"

        "cash diya"
        → mode: "cash"

        "branch mein kiya"
        → mode: "branch"

        "outlet mein payment ki"
        → mode: "outlet"

        "auto debit hota hai"
        → mode: "nach"


        ========================
        UNCLEAR CASES
        ========================

        If the response:
        - Does not mention payment method
        - Is ambiguous or unrelated
        - User says "yaad nahi", "pata nahi"

        Examples:
        "याद नहीं",
        "पता नहीं",
        "समझ नहीं आया"

        → is_clear = false

        ========================
        IMPORTANT INSTRUCTIONS
        ========================

        - Choose the BEST matching mode
        - Be lenient (e.g., just "online" → online_lan)
        - Do NOT guess if unclear
        - Do NOT explain reasoning
        - Do NOT add extra fields
        - Return ONLY valid JSON

        ========================
        OUTPUT FORMAT (STRICT)
        ========================

        {
        "value": {
            "mode": "online_lan/online_field_executive/cash/branch/outlet/nach"
        },
        "is_clear": true/false
        }
    """



def handle(user_input, session):
    r = call_gemini(PROMPT + user_input)
    if not r["is_clear"]:
        return QuestionResult(False)
    session["mode_of_payment"] = r["value"].get("mode")
    if r["value"].get("field_executive_name"):
        session["field_executive_name"] = r["value"].get("field_executive_name")
    if r["value"].get("field_executive_contact"):
        session["field_executive_contact"] = r["value"].get("field_executive_contact")
    return QuestionResult(True)

