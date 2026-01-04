from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    return "Vastav mein kitna bhugtan kiya gaya tha? Kripya rashi bataiye taaki hum use darj kar saken."


PROMPT = """
    You are an intelligent assistant. 
    question asked : "Vastav mein kitna bhugtan kiya gaya tha? Kripya rashi (amount) bataiye taaki hum use darj kar saken."
    
    Extract the payment amount in numeric format from the user's response.
    
    examples:
    user-response: "Pachas hazaar rupaye"
    value: "50000"
    
    user-response: "Ek lakh rupaye"
    value: "100000"
    
    user-response: "Dus hazaar"
    value: "10000"

    IMPORTANT: Return ONLY valid JSON, no markdown, no code blocks, no explanations.
    
    Return JSON:
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

