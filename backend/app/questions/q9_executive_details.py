from .base import QuestionResult
from ..llm.gemini_client import call_gemini


def get_text():
    return "क्या आप मुझे फील्ड एग्ज़ीक्यूटिव का नाम और नंबर बता सकते हैं?"


PROMPT = """
    You are an intelligent assistant. 
    question asked : "Kya aap mujhe field executive ka naam or number bta sakte h?"
    
    Extract the field executive name and contact number from the user's response.

    ========================
    IMPORTANT RULES
    ========================
    
    1. If user provides name and/or number:
       - Extract and return the values
       - Set is_clear = true
    
    2. If user says they DON'T KNOW (this is a VALID response):
       - Examples: "nahi pta", "nahi muje naam ni pta", "muje pta nahi", "don't know", 
         "nahi janta", "muje naam nahi pata", "number nahi pata", "I don't know"
       - Return null for both fields
       - Set is_clear = true (this is a valid answer, not unclear)
    
    3. Only set is_clear = false if the response is completely unrelated or meaningless
    
    ========================
    EXAMPLES
    ========================
    
    "Rahul Sharma, 9876543210"
    → field_executive_name: "Rahul Sharma"
    → field_executive_contact: "9876543210"
    → is_clear: true
    
    "nahi muje naam ni pta"
    → field_executive_name: null
    → field_executive_contact: null
    → is_clear: true
    
    "nahi pta"
    → field_executive_name: null
    → field_executive_contact: null
    → is_clear: true
    
    "Rahul ka number hai 9876543210"
    → field_executive_name: "Rahul"
    → field_executive_contact: "9876543210"
    → is_clear: true
    
    ========================
    OUTPUT FORMAT
    ========================
    
    IMPORTANT: Return ONLY valid JSON, no markdown, no code blocks, no explanations.
    
    {
    "value": {
        "field_executive_name": "name or null",
        "field_executive_contact": "contact number or null"
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

