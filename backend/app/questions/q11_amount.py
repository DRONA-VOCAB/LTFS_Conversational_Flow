from .base import QuestionResult
from ..llm.gemini_client import call_gemini


def get_text():
    return "वस्तव में कितना भुगतान किया गया था? कृपया राशि बताइए ताकि हम उसे दर्ज कर सकें."


PROMPT = """
        You are an intelligent assistant.

        Question asked to the user:
        "वास्तव में कितना भुगतान किया गया था? कृपया राशि बताइए ताकि हम उसे दर्ज कर सकें।"

        Your task is to extract the PAYMENT AMOUNT from the user's response and return it
        as a NUMERIC STRING (digits only).

        ========================
        AMOUNT EXTRACTION RULES
        ========================

        - Extract the amount as numbers only (no commas, no currency symbols).
        - Amount may be expressed as:
        - Spoken numbers in Hindi or Hinglish
        - Numeric values (e.g., 5000, 50,000)
        - Words like हजार, लाख, रुपये, पैसा
        - Ignore words like "रुपये", "₹", "rs", "rupees".

        - Common mappings:
        - हजार / hazaar → ×1,000
        - लाख / lakh → ×100,000

        ========================
        EXAMPLES (DEVANAGARI FIRST)
        ========================

        "पचास हजार रुपये"
        → value: "50000"

        "एक लाख रुपये"
        → value: "100000"

        "दस हजार"
        → value: "10000"

        "बीस हज़ार पाँच सौ"
        → value: "20500"

        "₹ 15,000"
        → value: "15000"

        "पंद्रह सौ"
        → value: "1500"


        Roman examples:
        "pachas hazaar rupaye"
        → value: "50000"

        "ek lakh rupees"
        → value: "100000"

        "dus hazaar"
        → value: "10000"

        "bees hazaar paanch sau"
        → value: "20500"

        "15000"
        → value: "15000"

        "rs 2500"
        → value: "2500"


        ========================
        UNCLEAR CASES
        ========================

        If the response:
        - Does not mention an amount
        - Mentions a range ("10–15 हजार")
        - Uses vague terms ("थोड़ा सा", "जितना बन पड़ा")
        - Is unrelated or unclear

        Examples:
        "याद नहीं",
        "पता नहीं",
        "ठीक से याद नहीं है"

        → value = null
        → is_clear = false

        ========================
        IMPORTANT INSTRUCTIONS
        ========================

        - Return ONLY the numeric amount as a string
        - Do NOT guess or assume
        - If amount is clearly extracted → is_clear = true
        - If unclear or missing → is_clear = false
        - Do NOT explain your reasoning
        - Do NOT add extra fields
        - Return ONLY valid JSON (no markdown, no text outside JSON)

        ========================
        OUTPUT FORMAT (STRICT)
        ========================

        {
        "value": "numeric_amount_as_string",
        "is_clear": true/false
        }
"""


def handle(user_input, session):
    r = call_gemini(PROMPT + user_input)
    if not r["is_clear"]:
        return QuestionResult(False)
    session["amount"] = r["value"]
    return QuestionResult(True)
