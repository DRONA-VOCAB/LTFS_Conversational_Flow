from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    return "नमस्ते, मैं L and T finance की तरफ़ से बात कर रही हूँ, क्या मेरी बात {{customer_name}} जी से हो रही है?"


PROMPT = """
    You are an intelligent assistant. Your task is to classify the user's response for identity confirmation
    (whether the user confirms they are the intended person).

    ========================
    CLASSIFICATION RULES
    ========================

    YES → User confirms identity.
    Be VERY lenient. Even short or casual confirmations count.

    Devanagari (priority examples):
    "हाँ", "हां", "हाँ जी", "हां जी", "हा", "हाँ बिल्कुल", "बिल्कुल", "सही है", "ठीक है",
    "मैं ही हूँ", "मैं ही हूं", "जी हाँ", "जी", "जी बिल्कुल"

    Roman / English examples:
    "haa", "haan", "haaa", "ha", "han",
    "yes", "y", "yeah", "yep",
    "main hi hoon", "main hi hu",
    "bilkul", "sahi hai", "theek hai"


    NO → User denies identity or says they are someone else.

    Devanagari (priority examples):
    "नहीं", "नही", "ना", "नहीं जी",
    "मैं नहीं हूँ", "मैं वो नहीं हूँ",
    "मैं उनकी बेटी हूँ", "मैं उनका बेटा हूँ",
    "यह गलत है", "वो व्यक्ति मैं नहीं हूँ"

    Roman / English examples:
    "nhi", "nahi", "na", "no", "nope",
    "main nahi hoon", "main wo nahi hu",
    "main santhosh nahi hu",
    "galat", "wrong number"


    UNCLEAR → Response is completely unrelated, meaningless, or does not answer identity confirmation.

    Examples:
    "क्या?", "कौन?", "क्या बोल रहे हो?",
    "busy hoon", "call later",
    "sorry", "hello",
    random words, emojis, silence, or noise


    ========================
    IMPORTANT INSTRUCTIONS
    ========================

    - Prefer YES or NO whenever possible
    - Use UNCLEAR ONLY if the response is truly unrelated
    - Do NOT explain your reasoning
    - Do NOT add extra fields
    - Do NOT add markdown or text outside JSON
    - Return ONLY valid JSON

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
    session["identify_confirmation"] = r["value"]
    return QuestionResult(True)
