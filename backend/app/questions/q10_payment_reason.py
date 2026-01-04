from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    return "Bhugtan kis karan se kiya gaya tha?"


PROMPT = """
    You are an intelligent assistant. 
    question asked : "Bhugtan (payment) kis karan se kiya gaya tha?"
    
    Options:
    1. EMI
    2. EMI + Shulk (EMI + Charges)
    3. Settlement
    4. Foreclosure
    5. Shulk (Charges)
    6. Loan raddikaran (Loan Cancellation)
    7. Agrim (advance) EMI (Advance EMI)
    
    Extract the payment reason option from the user's response.

    IMPORTANT: Return ONLY valid JSON, no markdown, no code blocks, no explanations.
    
    Return JSON:
        {
        "value": "emi/emi_charges/settlement/foreclosure/charges/loan_cancellation/advance_emi",
        "is_clear": true/false
        }
"""


def handle(user_input, session):
    r = call_gemini(PROMPT + user_input)
    if not r["is_clear"]:
        return QuestionResult(False)
    session["reason"] = r["value"]
    return QuestionResult(True)

