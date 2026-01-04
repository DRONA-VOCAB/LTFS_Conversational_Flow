from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    return "मैं L and T Finance की तरफ़ से बात कर रही हूँ।  यह कॉल आपके personal loan ya Two Wheeler Loan के भुगतान अनुभव को समझने के लिए है। क्या आपने L and T Finance से Loan लिया है?"


PROMPT = """
    You are an intelligent assistant. Your task is to extract if the user confirmed that they have taken a loan from L and T Finance.

    examples:
    YES: "Haa", "Haan", "Haaa", "Ha", "Yes", "Haa mene L and T Finance se loan liya hai", "Haan maine loan liya hai", "Bilkul", "Sahi hai", "Haa mene loan liya hai"
    NO: "Nahi", "Nahi mene loan nahi liya", "Wrong number hai", "Galat number hai", "Maine loan nahi liya", "Nahi maine loan nahi liya wrong number hai"
    UNCLEAR: "Yaad ni aa rha", completely unrelated responses

    IMPORTANT: 
    - Accept variations: "haa", "haan", "haaa", "ha", "yes", "y" → all should be YES
    - If user says "wrong number", "galat number", "wrong number hai", "nhi mene loan ni liya wrong number hai" → classify as NO
    - If user clearly says they didn't take a loan → classify as NO
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
    session["loan_taken"] = r["value"]

    # If user says they didn't take a loan or it's a wrong number, end the call
    if r["value"] == "NO":
        session["call_should_end"] = True

    return QuestionResult(True)
