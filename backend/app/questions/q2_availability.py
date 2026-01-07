from app.questions.base import QuestionResult
from app.llm.gemini_client import call_gemini
from app.config.settings import COMPANY_NAME_FORMAL, get_message


def get_text():
    customer_name = "{{customer_name}}"
    return f"कृपया बताइए कि {customer_name} जी से किस समय बात करना ठीक रहेगा? अगर कोई दूसरा नंबर हो तो वह भी बता दीजिए।"


def _get_prompt_template():
    """Get the prompt template with dynamic company name"""
    return f"""
You are an intelligent conversational AI assistant for {COMPANY_NAME_FORMAL} conducting a customer survey call.

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
   Action: NEXT (proceed to next question)
   Response: null

2. "ROLE_CLARIFICATION" → caller asks about who you are, why calling, etc.
   Action: CLARIFY (provide explanation, then repeat question)
   Response: Generate friendly Hindi explanation of your role, then repeat the availability question

3. "REFUSE" → caller explicitly refuses to participate
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
  "action": "NEXT" | "CLARIFY" | "REPEAT" | "CLOSING",
  "response_text": "string or null"
}

CRITICAL GUIDELINES:
- If caller provides time/contact info → ANSWERED, action=NEXT, response_text=null
- If caller asks about role/purpose → ROLE_CLARIFICATION, action=CLARIFY, generate response
- If caller refuses → REFUSE, action=CLOSING, generate closing message
- If caller says they don't know who {{customer_name}} is → CONFUSED_ABOUT_CUSTOMER, action=CLOSING, generate closing message
- If caller asks off-topic → OFF_TOPIC, action=CLARIFY, redirect politely
- If unclear → UNCLEAR, action=REPEAT, generate clarification request
- All response_text should be in natural, conversational Hindi (Devanagari script)
- Include customer name when repeating questions
- IMPORTANT: "मुझे पता नहीं है" alone means "I don't know" (about availability) - this is UNCLEAR, not CONFUSED_ABOUT_CUSTOMER
- CONFUSED_ABOUT_CUSTOMER is specifically when they say they don't know WHO the person is
"""


def handle(user_input, session):
    """Handle user input using LLM to decide classification, action, and response"""
    customer_name = session.get("customer_name", "ग्राहक")
    
    # Get prompt template and replace placeholder with actual customer name
    PROMPT = _get_prompt_template()
    prompt_with_name = PROMPT.replace("{{customer_name}}", customer_name)
    
    r = call_gemini(prompt_with_name + "\n\nCaller's reply: " + user_input)
    
    print(f"DEBUG q2_availability LLM response: {r}")
    
    classification = r.get("classification", "UNCLEAR")
    is_clear = r.get("is_clear", False)
    action = r.get("action", "REPEAT")
    response_text = r.get("response_text")
    value = r.get("value", {})
    
    # Store extracted data
    if classification == "ANSWERED" and value:
        session["availability"] = value.get("preferred_time")
        session["user_contact"] = value.get("alternate_contact")

        # If identity was NO and we got contact info, end call
    if session.get("identify_confirmation") == "NO":
        if session["user_contact"] or session["availability"]:
            session["call_should_end"] = True
            action = "CLOSING"
            if not response_text:
                response_text = get_message("availability_contact_provided")
    
    if not is_clear and classification != "ANSWERED":
        print(f"DEBUG: LLM returned unclear response for: '{user_input}'")
        if action == "REPEAT" and response_text:
            session["needs_clarification"] = True
            session["clarification_response"] = response_text
            return QuestionResult(True, value=classification, extra={"action": action, "response_text": response_text})
        return QuestionResult(False)
    
    print(f"DEBUG: LLM classified '{user_input}' as: {classification}, action: {action}")
    
    # Store LLM's decision
    session["llm_action"] = action
    session["llm_response_text"] = response_text
    
    # Handle based on classification
    if classification == "ROLE_CLARIFICATION":
        session["needs_role_clarification"] = True
        if response_text:
            session["role_clarification_response"] = response_text
        return QuestionResult(True, value="ROLE_CLARIFICATION", extra={"action": action, "response_text": response_text})
    
    if classification == "CONFUSED_ABOUT_CUSTOMER":
        # Caller doesn't know who the customer is - end call gracefully
        session["call_should_end"] = True
        if response_text:
            session["closing_message"] = response_text
        else:
            session["closing_message"] = get_message("confused_about_customer")
        return QuestionResult(True, value="REFUSE", extra={"action": "CLOSING", "response_text": session["closing_message"]})
    
    if classification == "REFUSE" or action == "CLOSING":
        session["call_should_end"] = True
        if response_text:
            session["closing_message"] = response_text
        return QuestionResult(True, value="REFUSE", extra={"action": action, "response_text": response_text})
    
    if classification == "OFF_TOPIC":
        session["needs_clarification"] = True
        if response_text:
            session["clarification_response"] = response_text
        return QuestionResult(True, value="OFF_TOPIC", extra={"action": action, "response_text": response_text})
    
    if classification == "UNCLEAR":
        if response_text:
            session["needs_clarification"] = True
            session["clarification_response"] = response_text
        return QuestionResult(True, value="UNCLEAR", extra={"action": action, "response_text": response_text})
    
    # ANSWERED - proceed normally
    return QuestionResult(True, value="ANSWERED", extra={"action": action})
