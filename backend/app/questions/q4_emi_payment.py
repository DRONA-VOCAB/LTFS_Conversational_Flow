from .base import QuestionResult
from ..llm.gemini_client import call_gemini


def get_text():
    return "क्या आपने पिछले महीने भुगतान किया था?"


PROMPT = """
        You are an intelligent assistant. Your task is to classify whether the user confirms
        that they have paid the EMI / payment for the previous month.

        ========================
        CLASSIFICATION RULES
        ========================

        YES → User confirms payment was made for the previous month.
        Be VERY lenient. Even short or casual confirmations count.

        Devanagari examples (priority):
        "हाँ", "हां", "हाँ जी", "जी हाँ", "हाँ बिल्कुल", "बिल्कुल", "सही है",
        "हाँ मैंने पिछले महीने भुगतान किया था",
        "हाँ, पेमेंट किया था",
        "पिछले महीने ईएमआई भर दी थी",
        "जी, पेमेंट हो गया था"

        Roman / English examples:
        "haa", "haan", "haaa", "ha", "han",
        "yes", "y", "yeah", "yep",
        "haa mene payment kiya tha pichle mahine",
        "haan pichle mahine EMI bhar di thi",
        "bilkul", "sahi hai"


        NO → User says payment was NOT made.

        Devanagari examples (priority):
        "नहीं", "नही", "ना",
        "नहीं मैंने भुगतान नहीं किया",
        "पिछले महीने पेमेंट नहीं हुआ",
        "ईएमआई नहीं भरी थी",
        "नहीं किया था"

        Roman / English examples:
        "nahi", "nhi", "na", "no",
        "nahi maine payment nahi kiya",
        "pichle mahine EMI nahi bhari",
        "nahi kiya tha"


        UNCLEAR → User is unsure or response is unrelated.

        Examples:
        "याद नहीं आ रहा",
        "शायद किया होगा",
        "पक्का नहीं कह सकता",
        "देखना पड़ेगा",
        "अभी याद नहीं है",
        unrelated responses, silence, or noise


        ========================
        IMPORTANT INSTRUCTIONS
        ========================

        - Prefer YES or NO whenever possible
        - Use UNCLEAR only if the response is truly unclear or unrelated
        - Do NOT guess or infer intent
        - Do NOT explain your reasoning
        - Do NOT add extra fields
        - Return ONLY valid JSON (no markdown, no text outside JSON)

        ========================
        OUTPUT FORMAT (STRICT)
        ========================

        {
        "value": "YES/NO/UNCLEAR",
        "is_clear": true/false
        }

        Rules:
        - is_clear = true for YES or NO
        - is_clear = false only for UNCLEAR
    """


def handle(user_input, session):
    r = call_gemini(PROMPT + user_input)
    if not r["is_clear"]:
        return QuestionResult(False)
    session["last_month_emi_payment"] = r["value"]
    return QuestionResult(True)
