from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    return "Kripya bataiye, is account ka bhugtan kisne kiya hai? Kya main bhugtan karta ka naam aur sampark number note kar sakta hoon?"


PROMPT = """
    You are an intelligent assistant. 
    question asked : "Kripya bataiye, is account ka bhugtan kisne kiya hai? Kya main bhugtan karta ka naam aur sampark number note kar sakta hoon?"
    
    Extract the payee name and contact number from the user's response.

    IMPORTANT: Return ONLY valid JSON, no markdown, no code blocks, no explanations.
    
    Return JSON:
        {
        "value": {
            "payee_name": "name of the person who made payment",
            "payee_contact": "contact number if provided"
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

