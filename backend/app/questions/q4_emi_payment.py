from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    return "Kya aapne pichle mahine bhugtan kiya tha?"


PROMPT = """
    You are an intelligent assistant. Your task is to extract if the user confirmed that they have paid the EMI/payment for the previous month or not.

    examples:
    YES: "Haa", "Haan", "Haaa", "Ha", "Yes", "Haa mene payment kiya tha pichle mahine", "Bilkul", "Sahi hai", "Haa kiya tha"
    NO: "Nahi", "Nahi mene payment nahi kiya tha pichle mahine", "Nahi kiya"
    UNCLEAR: "Yaad ni aa rha kiya hi hoga", completely unrelated responses

    IMPORTANT: 
    - Accept variations: "haa", "haan", "haaa", "ha", "yes", "y" → all should be YES
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
    session["last_month_emi_payment"] = r["value"]
    return QuestionResult(True)

