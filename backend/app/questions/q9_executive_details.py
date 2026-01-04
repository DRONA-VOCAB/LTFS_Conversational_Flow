from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    return "Kya aap mujhe kisi field executive ka naam or number bta sakte h?"


PROMPT = """
    You are an intelligent assistant. 
    question asked : "Kya aap mujhe kisi field executive ka naam or number bta sakte h?"
    
    Extract the field executive name and contact number from the user's response.

    IMPORTANT: Return ONLY valid JSON, no markdown, no code blocks, no explanations.
    
    Return JSON:
        {
        "value": {
            "field_executive_name": "name",
            "field_executive_contact": "contact number"
        },
        "is_clear": true/false
        }
"""


def handle(user_input, session):
    r = call_gemini(PROMPT + user_input)
    if not r["is_clear"]:
        return QuestionResult(False)
    if r["value"].get("field_executive_name"):
        session["field_executive_name"] = r["value"].get("field_executive_name")
    if r["value"].get("field_executive_contact"):
        session["field_executive_contact"] = r["value"].get("field_executive_contact")
    return QuestionResult(True)

