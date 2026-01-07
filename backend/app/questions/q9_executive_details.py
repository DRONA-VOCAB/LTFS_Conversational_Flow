from app.questions.base import QuestionResult
from app.llm.gemini_client import call_gemini
from app.config.settings import COMPANY_NAME_FORMAL


def get_text():
    return "क्या आप मुझे फील्ड एग्ज़ीक्यूटिव का नाम और नंबर बता सकते हैं?"


def _get_prompt_template():
    """Get the prompt template with dynamic company name"""
    return f"""
You are an intelligent conversational AI assistant for {COMPANY_NAME_FORMAL} conducting a customer survey call.

The agent just asked:
"क्या आप मुझे फील्ड एग्ज़ीक्यूटिव का नाम और नंबर बता सकते हैं?"

You receive the caller's reply (in Hindi, Hinglish, or English).

Your task is to:
1. Understand the caller's intent completely
2. Extract executive details OR handle out-of-bound questions
3. Decide what action to take next
4. Generate an appropriate response if needed

MAIN TASK - Extract information:
- field_executive_name: name of field executive, or null
- field_executive_contact: contact number (digits only), or null
- Note: If caller says "don't know" or "not available", accept as valid (set both to null, is_clear=true)

OUT-OF-BOUND HANDLING:
If the caller asks questions NOT related to executive details (e.g., "कौन हो आप?", "क्यों कॉल कर रहे हो?", 
asks about amount, date, etc.), classify as:
- "ROLE_CLARIFICATION" → asking about who you are, why calling, etc. (cooperative)
- "OFF_TOPIC" → asking about something else - redirect politely

CLASSIFICATION CATEGORIES:

1. "ANSWERED" → caller provided name/contact OR said they don't know
   Action: NEXT (proceed to next question)
   Response: null

2. "ROLE_CLARIFICATION" → caller asks about who you are, why calling, etc.
   Action: CLARIFY (provide explanation, then repeat question)
   Response: Generate friendly Hindi explanation of your role, then repeat the executive details question

3. "REFUSE" → caller explicitly refuses to participate
   Action: CLOSING (end call gracefully)
   Response: Generate polite closing message in Hindi

4. "OFF_TOPIC" → caller asks about something else (amount, date, etc.)
   Action: CLARIFY (acknowledge and redirect)
   Response: Generate polite Hindi response acknowledging their question, explaining you'll get to that, 
   and asking the executive details question again

5. "UNCLEAR" → reply is too ambiguous or unrelated
   Action: REPEAT (ask question again)
   Response: Generate polite request to repeat the answer in Hindi

Return ONLY this JSON (no extra text):
{
  "value": {
    "field_executive_name": "string or null",
    "field_executive_contact": "string or null"
  },
  "classification": "ANSWERED" | "ROLE_CLARIFICATION" | "REFUSE" | "OFF_TOPIC" | "UNCLEAR",
  "is_clear": true | false,
  "action": "NEXT" | "CLARIFY" | "REPEAT" | "CLOSING",
  "response_text": "string or null"
}

CRITICAL GUIDELINES:
- If caller provides name/contact OR says "don't know" → ANSWERED, action=NEXT, response_text=null
- If caller asks about role → ROLE_CLARIFICATION, action=CLARIFY, generate response
- If caller refuses → REFUSE, action=CLOSING, generate closing message
- If caller asks off-topic → OFF_TOPIC, action=CLARIFY, redirect politely
- If unclear → UNCLEAR, action=REPEAT, generate clarification request
- All response_text should be in natural, conversational Hindi (Devanagari script)
"""


def handle(user_input, session):
    """Handle user input using LLM to decide classification, action, and response"""
    PROMPT = _get_prompt_template()
    r = call_gemini(PROMPT + "\n\nCaller's reply: " + user_input)
    
    print(f"DEBUG q9_executive_details LLM response: {r}")
    
    classification = r.get("classification", "UNCLEAR")
    is_clear = r.get("is_clear", False)
    action = r.get("action", "REPEAT")
    response_text = r.get("response_text")
    value = r.get("value", {})
    
    # Store extracted data
    if classification == "ANSWERED" and value:
        if value.get("field_executive_name"):
            session["field_executive_name"] = value.get("field_executive_name")
        if value.get("field_executive_contact"):
            session["field_executive_contact"] = value.get("field_executive_contact")
    
    if not is_clear and classification != "ANSWERED":
        print(f"DEBUG: LLM returned unclear response for: '{user_input}'")
        if action == "REPEAT" and response_text:
            session["needs_clarification"] = True
            session["clarification_response"] = response_text
            return QuestionResult(True, value="UNCLEAR", extra={"action": action, "response_text": response_text})
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
