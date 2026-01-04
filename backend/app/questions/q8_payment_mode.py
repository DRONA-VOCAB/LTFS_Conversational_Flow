from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    return "Bhugtan kis madhyam se kiya gaya tha? Aapne online, UPI ya nagad diya tha?"


PROMPT = """
    You are an intelligent assistant. 
    question asked : "Bhugtan (payment) kis madhyam se kiya gaya tha?"
    
    Options:
    1. online_lan - for "online", "upi", "neft", "rtgs", "internet banking", "online kiya", "online se", "online madhyam se"
    2. online_field_executive - for "field executive ko", "executive ko online", "field executive se"
    3. cash - for "cash", "nagad", "nakad", "cash diya"
    4. branch - for "branch", "shakha", "branch mein", "bank mein"
    5. outlet - for "outlet", "outlet mein"
    6. nach - for "nach", "automated", "auto debit"
    
    Extract the payment mode option from the user's response.

    IMPORTANT: 
    - "online", "online kiya", "online se", "online madhyam se", "upi", "internet banking" → all should map to "online_lan"
    - Be lenient - if user just says "online", it means "online_lan"
    - Return ONLY valid JSON, no markdown, no code blocks, no explanations.
        
    Return JSON:
        {
        "value": {
            "mode": "online_lan/online_field_executive/cash/branch/outlet/nach"
        },
        "is_clear": true/false
        }
"""


def handle(user_input, session):
    r = call_gemini(PROMPT + user_input)
    if not r["is_clear"]:
        return QuestionResult(False)
    session["mode_of_payment"] = r["value"].get("mode")
    if r["value"].get("field_executive_name"):
        session["field_executive_name"] = r["value"].get("field_executive_name")
    if r["value"].get("field_executive_contact"):
        session["field_executive_contact"] = r["value"].get("field_executive_contact")
    return QuestionResult(True)

