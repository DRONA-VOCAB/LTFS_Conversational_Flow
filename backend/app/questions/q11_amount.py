from app.questions.base import QuestionResult
from app.llm.gemini_client import call_gemini
from app.config.settings import COMPANY_NAME_FORMAL


def get_text():
    return "वस्तव में कितना भुगतान किया गया था? कृपया राशि बताइए ताकि हम उसे दर्ज कर सकें."


def _get_prompt_template():
    """Get the prompt template with dynamic company name"""
    return f"""
You are an intelligent conversational AI assistant for {COMPANY_NAME_FORMAL} conducting a customer survey call.

The agent just asked:
"वास्तव में कितना भुगतान किया गया था? कृपया राशि बताइए ताकि हम उसे दर्ज कर सकें।"

You receive the caller's reply (in Hindi, Hinglish, or English), which may describe an amount in words or digits.

Your task is to:
1. Understand the caller's intent completely
2. Extract payment amount OR handle out-of-bound questions
3. Decide what action to take next
4. Generate an appropriate response if needed

MAIN TASK - Extract amount:
- Extract payment amount as digits only (no commas, no currency symbols)
- Examples: "पचास हजार" → "50000", "25 हज़ार" → "25000", "10k" → "10000"
- Ignore currency words like रुपये / rupees / rs / ₹

OUT-OF-BOUND HANDLING:
If the caller asks questions NOT related to payment amount (e.g., "कौन हो आप?", "क्यों कॉल कर रहे हो?", 
asks about date, mode, etc.), classify as:
- "ROLE_CLARIFICATION" → asking about who you are, why calling, etc. (cooperative)
- "OFF_TOPIC" → asking about something else - redirect politely

CLASSIFICATION CATEGORIES:

1. "ANSWERED" → caller clearly provided payment amount
   Action: NEXT (proceed to summary)
   Response: null

2. "ROLE_CLARIFICATION" → caller asks about who you are, why calling, etc.
   Action: CLARIFY (provide explanation, then repeat question)
   Response: Generate friendly Hindi explanation of your role, then repeat the amount question

3. "REFUSE" → caller explicitly refuses to participate
   Action: CLOSING (end call gracefully)
   Response: Generate polite closing message in Hindi

4. "OFF_TOPIC" → caller asks about something else (date, mode, etc.)
   Action: CLARIFY (acknowledge and redirect)
   Response: Generate polite Hindi response acknowledging their question, explaining you'll get to that, 
   and asking the amount question again

5. "UNCLEAR" → reply is too ambiguous or unrelated
   Action: REPEAT (ask question again)
   Response: Generate polite request to repeat the answer in Hindi

Return ONLY this JSON (no extra text):
{
  "value": "numeric_amount_as_string or null",
  "classification": "ANSWERED" | "ROLE_CLARIFICATION" | "REFUSE" | "OFF_TOPIC" | "UNCLEAR",
  "is_clear": true | false,
  "action": "NEXT" | "CLARIFY" | "REPEAT" | "CLOSING",
  "response_text": "string or null"
}

CRITICAL GUIDELINES:
- If caller provides amount → ANSWERED, action=NEXT, response_text=null
- Amount should be digits only (e.g., "50000" not "50,000" or "₹50000")
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
    
    print(f"DEBUG q11_amount LLM response: {r}")
    
    classification = r.get("classification", "UNCLEAR")
    is_clear = r.get("is_clear", False)
    action = r.get("action", "REPEAT")
    response_text = r.get("response_text")
    value = r.get("value")
    
    # Store extracted data
    if classification == "ANSWERED" and value:
        session["amount"] = value
    
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
