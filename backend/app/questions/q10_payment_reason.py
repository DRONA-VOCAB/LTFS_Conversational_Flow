from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    return "भुगतान किस कारण से किया गया था?"


PROMPT = """
    You are an intelligent assistant.

    Question asked:
    "भुगतान किस कारण से किया गया था?"

    Your task is to extract the PAYMENT REASON from the user's response.

    ========================
    PAYMENT REASON OPTIONS
    ========================
    emi
    emi_charges
    settlement
    foreclosure
    charges
    loan_cancellation
    advance_emi

    ========================
    MAPPING HINTS
    ========================
    emi → ईएमआई, किस्त, मंथली किस्त, regular payment
    emi_charges → EMI + charge, penalty ke sath EMI, late fee
    settlement → settlement, OTS, one time settlement
    foreclosure → loan close, full and final, poora loan
    charges → penalty, late fee, bounce charge, sirf charge
    loan_cancellation → loan cancel, loan radd
    advance_emi → advance EMI, agrim kisht, future EMI

    ========================
    EXAMPLES (DEVANAGARI)
    ========================
    "ईएमआई के लिए किया" → emi  
    "ईएमआई और चार्ज दिए" → emi_charges  
    "सेटलमेंट के लिए" → settlement  
    "पूरा लोन बंद किया" → foreclosure  
    "केवल पेनल्टी" → charges  
    "लोन रद्द करने के लिए" → loan_cancellation  
    "अग्रिम ईएमआई" → advance_emi  

    Roman examples:
    "emi ke liye" → emi  
    "loan close karne ke liye" → foreclosure  
    "advance emi di" → advance_emi  

    ========================
    UNCLEAR
    ========================
    If unclear, unrelated, or not mentioned → is_clear = false

    ========================
    RETURN JSON ONLY
    ========================
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
