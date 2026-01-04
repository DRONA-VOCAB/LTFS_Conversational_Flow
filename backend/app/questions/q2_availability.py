from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    customer_name = "{{customer_name}}"
    return f"Kripya bataiye ki shriman/shrimati {customer_name} ji se kis samay par sampark karna uchit rahega? Sath hi, yadi koi alternate number uplabdh ho to kripya share karein."


PROMPT = """
    You are an intelligent assistant. Your task is to extract availability information and alternate contact number from the user's response.
    
    Extract:
    1. Preferred time to connect (if mentioned) - extract any time reference like "5 baje", "5pm", "evening", "morning", "abhi", "now"
    2. Alternate contact number (if provided) - extract any phone number, even if it's just digits like "123456789"
    
    Examples:
    - "123456789 ye unka number h" → alternate_contact: "123456789"
    - "9876543210" → alternate_contact: "9876543210"
    - "wo 5bje available hongi" → preferred_time: "5 baje" or "5pm"
    - "abhi phone kar lijiye" → preferred_time: "now" or "immediately"
    - "isi same number pr call kr dena" → preferred_time: "now" (if time not mentioned, but indicates availability)
    
    IMPORTANT: Return ONLY valid JSON, no markdown, no code blocks, no explanations.
    
    Return JSON:
        {
        "value": {
            "preferred_time": "time mentioned or null",
            "alternate_contact": "phone number or null"
        },
        "is_clear": true/false
        }
"""


def handle(user_input, session):
    r = call_gemini(PROMPT + user_input)
    if not r["is_clear"]:
        return QuestionResult(False)
    session["availability"] = r["value"].get("preferred_time")
    session["user_contact"] = r["value"].get("alternate_contact")

    # If identity is NO and either alternate contact or availability/time is provided, end the call
    if session.get("identify_confirmation") == "NO":
        if session["user_contact"] or session["availability"]:
            session["call_should_end"] = True

    return QuestionResult(True)
