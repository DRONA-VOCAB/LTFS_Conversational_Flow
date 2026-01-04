from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    return "नमस्ते, मैं L and T finance की तरफ़ से बात कर रही हूँ, क्या मेरी बात {{customer_name}} जी से हो रही है?"


PROMPT = """
        You are an intelligent assistant. Your task is to classify the user's response for identity confirmation.
        Classify response for identity confirmation.

        YES → user confirms name (examples: "haa", "haan", "haaa", "ha", "yes", "y", "main hi hoon", "bilkul", "sahi hai", "theek hai")
        NO → wrong person (examples: "nhi", "nahi", "no", "galat", "wo nahi hai", "main unki beti hu", "main santhosh nhi hu")
        UNCLEAR → completely unrelated responses

        IMPORTANT: 
        - Accept variations: "haa", "haan", "haaa", "ha", "yes", "y" → all should be YES
        - "nhi", "nahi", "no" should always be classified as NO
        - If user says they are someone else (like "main unki beti hu", "main santhosh nhi hu"), classify as NO
        - Be lenient with YES responses - even simple "haa" or "haan" should be accepted as YES
        - Only mark as UNCLEAR if the response is completely unrelated or truly unclear
        - Return ONLY valid JSON, no markdown, no code blocks, no explanations.

        Return JSON:
        {
        "value": "YES/NO/UNCLEAR",
        "is_clear": true/false
        }
"""


def handle(user_input, session):
    r = call_gemini(PROMPT + user_input)
    if not r["is_clear"]:
        return QuestionResult(False)
    session["identify_confirmation"] = r["value"]
    return QuestionResult(True)
