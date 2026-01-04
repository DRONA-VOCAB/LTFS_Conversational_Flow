from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    return "Is payment ko kisne kiya tha? Aap khud ya kisi aur ne?"


PROMPT = """
    You are an intelligent assistant. 
    question asked : "Is payment ko kisne kiya tha? Aap khud ya kisi aur ne?"

    Options:
    1. आपने स्वयं भुगतान किया। aapne khud kiya  
    2. किसी परिवार का सदस्य  
    3. ग्राहक के किसी मित्र  
    4. या फिर किसी और ने (third party)

    extract the option from the user's response.
    example:
    user-response: "Meri papa se kiya tha"
    value: "relative"
    
    user-response: "Main khud kiya"
    value: "self"

    IMPORTANT: Return ONLY valid JSON, no markdown, no code blocks, no explanations.
    
    Return JSON:
        {
        "value": "self/relative/friend/third_party",
        "is_clear": true/false
        }
"""


def handle(user_input, session):
    r = call_gemini(PROMPT + user_input)
    if not r["is_clear"]:
        return QuestionResult(False)
    session["payee"] = r["value"]
    return QuestionResult(True)
