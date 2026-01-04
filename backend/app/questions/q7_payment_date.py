from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    return "Aapne payment kis tareekh ko kiya tha?"


PROMPT = """
    You are an intelligent assistant. 
    question asked : "Aapne payment kis tareekh ko kiya tha?"

    extract the date in dd/mm/yyyy format from the user's response.
    example:
    user-response: "december 3 ko kiya tha"
    value: "03/12/2025"

    IMPORTANT: Return ONLY valid JSON, no markdown, no code blocks, no explanations.
    Take year either 2025 or 2026

    Return JSON:
        {
        "value": "dd/mm/yyyy",
        "is_clear": true/false
        }
"""


def handle(user_input, session):
    r = call_gemini(PROMPT + user_input)
    if not r["is_clear"]:
        return QuestionResult(False)
    session["pay_date"] = r["value"]
    return QuestionResult(True)
