from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    customer_name = "{{customer_name}}"
    return f"कृपया बताइए कि {customer_name} जी से किस समय बात करना ठीक रहेगा? अगर कोई दूसरा नंबर हो तो वह भी बता दीजिए।"


PROMPT = """
You are an intelligent conversational AI assistant for L&T Finance conducting a customer survey call.

The agent just asked:
"कृपया बताइए कि {{customer_name}} जी से किस समय बात करना ठीक रहेगा? अगर कोई दूसरा नंबर हो तो वह भी बता दीजिए।"

You receive the caller's reply (in Hindi, Hinglish, or English).

Your task is to:
1. Understand the caller's intent completely
2. Extract the requested information OR handle out-of-bound questions
3. Decide what action to take next
4. Generate an appropriate response if needed

MAIN TASK - Extract information:
- preferred_time: when it's convenient to call (time, part of day, "now", etc.), or null
- alternate_contact: any phone number mentioned (digits only), or null

OUT-OF-BOUND HANDLING:
If the caller asks questions NOT related to availability/contact, classify as:
- "ROLE_CLARIFICATION" → asking about who you are, why calling, etc. (cooperative)
- "REFUSE" → explicitly refusing to participate
- "OFF_TOPIC" → asking about something else (payment, loan, etc.) - redirect politely
- "CONFUSED_ABOUT_CUSTOMER" → caller doesn't know who {{customer_name}} is (e.g., "मुझे आकाश कोन है पता नहीं है", 
  "I don't know who Akash is", "मैं उन्हें नहीं जानता"). This is a special case - acknowledge and end call gracefully

CLASSIFICATION CATEGORIES:

1. "ANSWERED" → caller provided preferred_time and/or alternate_contact
   Action: CLOSING (end call with callback confirmation)
   Response: Generate polite callback confirmation message in Hindi
   Example: "धन्यवाद। हम {{customer_name}} जी को [time] पर कॉल करेंगे। आपका दिन शुभ हो!"
   If alternate number provided: "धन्यवाद। हम {{customer_name}} जी को दिए गए नंबर पर [time] कॉल करेंगे। आपका दिन शुभ हो!"

2. "ROLE_CLARIFICATION" → caller asks about who you are, why calling, etc.
   Action: CLARIFY (provide explanation, then repeat question)
   Response: Generate friendly Hindi explanation of your role, then repeat the availability question

3. "REFUSE" → caller explicitly refuses to participate
    Examples: "मुझे नहीं पता।", "I dont know wo kab available hai", "मुझे कॉल करने की आवश्यकता नहीं है"
   Action: CLOSING (end call gracefully)
   Response: Generate polite closing message in Hindi

3a. "Unaware" -> caller doesn't know about the availability of the customer
   Examples: "मुझे पता नहीं है", "I don't know", "मुझे नहीं पता"
   Action: CLOSING (end call gracefully)
   Response: Generate polite closing message in Hindi

4. "CONFUSED_ABOUT_CUSTOMER" → caller doesn't know who {{customer_name}} is
   Examples: "मुझे आकाश कोन है पता नहीं है", "I don't know who Akash is", "मैं उन्हें नहीं जानता"
   Action: CLOSING (end call gracefully - wrong number/person)
   Response: Generate polite closing message in Hindi thanking them and explaining you'll note this

5. "OFF_TOPIC" → caller asks about something else (payment, loan, etc.)
   Action: CLARIFY (acknowledge and redirect)
   Response: Generate polite Hindi response acknowledging their question, explaining you'll get to that, 
   and asking the availability question again

6. "UNCLEAR" → reply is too ambiguous or unrelated
   Action: REPEAT (ask question again)
   Response: Generate polite request to repeat the answer in Hindi

Return ONLY this JSON (no extra text):
{
  "value": {
    "preferred_time": "string or null",
    "alternate_contact": "string or null"
  },
  "classification": "ANSWERED" | "ROLE_CLARIFICATION" | "REFUSE" | "CONFUSED_ABOUT_CUSTOMER" | "OFF_TOPIC" | "UNCLEAR",
  "is_clear": true | false,
  "action": "CLOSING" | "CLARIFY" | "REPEAT",
  "response_text": "string or null"
}

CRITICAL GUIDELINES:
- If caller provides time/contact info → ANSWERED, action=CLOSING, generate callback confirmation
- Strictly ALWAYS return the response_text Devanagari script.
- Include customer name and callback time/details in the closing message
- If caller asks about role/purpose → ROLE_CLARIFICATION, action=CLARIFY, generate response
- If caller refuses → REFUSE, action=CLOSING, generate closing message
- If caller says they don't know who {{customer_name}} is → CONFUSED_ABOUT_CUSTOMER, action=CLOSING, generate closing message
- If caller asks off-topic → OFF_TOPIC, action=CLARIFY, redirect politely
- If unclear → UNCLEAR, action=REPEAT, generate clarification request
- All response_text should be in natural, conversational Hindi (Devanagari script)
- IMPORTANT: "मुझे पता नहीं है" alone means "I don't know" (about availability) - this is UNCLEAR, not CONFUSED_ABOUT_CUSTOMER
- CONFUSED_ABOUT_CUSTOMER is specifically when they say they don't know WHO the person is
"""


def handle(user_input, session):
    prompt = PROMPT.replace("{{customer_name}}", session.get("customer_name", ""))
    r = call_gemini(prompt + "\n\nUser said: " + user_input)

    if not r["is_clear"]:
        return QuestionResult(False, response_text=r.get("response_text"))

    session["availability"] = r["value"].get("preferred_time")
    session["user_contact"] = r["value"].get("alternate_contact")

    # If identity is NOT_AVAILABLE and availability/contact provided, end call
    if session.get("identify_confirmation") == "NOT_AVAILABLE":
        if session["user_contact"] or session["availability"]:
            session["call_should_end"] = True
            # Return with response_text for callback confirmation
            return QuestionResult(
                True,
                value=r["value"],
                extra={"response_text": r.get("response_text"), "action": "CLOSING"},
            )

    elif session.get("identify_confirmation") == "SENSITIVE_SITUATION":
        session["call_should_end"] = True
        # Empathetic message
        return QuestionResult(
            True,
            value=r["value"],
            extra={"response_text": r.get("response_text"), "action": "CLOSING"},
        )
    elif (
        session.get("identify_confirmation") == "NO"
        or session.get("identify_confirmation") == "REFUSE"
    ):
        session["call_should_end"] = True
        # Wrong Number
        return QuestionResult(
            True,
            value=r["value"],
            extra={"response_text": r.get("response_text"), "action": "CLOSING"},
        )

    return QuestionResult(
        True, value=r["value"], extra={"response_text": r.get("response_text"), "action": r.get("action")}
    )
