from app.questions.base import QuestionResult
from app.llm.gemini_client import call_gemini
from app.config.settings import COMPANY_NAME_FORMAL


def get_text():
    return "क्या आपने पिछले महीने भुगतान किया था?"


def _get_prompt_template():
    """Get the prompt template with dynamic company name"""
    return f"""
You are an intelligent conversational AI assistant for {COMPANY_NAME_FORMAL} conducting a customer survey call.

The agent just asked:
"क्या आपने पिछले महीने भुगतान किया था?"

You receive the caller's reply (in Hindi, Hinglish, or English).

Your task is to:
1. Understand the caller's intent completely
2. Classify the response OR handle out-of-bound questions
3. Decide what action to take next
4. Generate an appropriate response if needed

MAIN CLASSIFICATION:
- "YES" → caller confirms they paid last month
- "NO" → caller says they did NOT pay last month
- "UNCLEAR" → cannot determine from reply

OUT-OF-BOUND HANDLING:
If the caller asks questions NOT related to payment (e.g., "कौन हो आप?", "क्यों कॉल कर रहे हो?", 
asks about loan details, etc.), classify as:
- "ROLE_CLARIFICATION" → asking about who you are, why calling, etc. (cooperative)
- "OFF_TOPIC" → asking about something else - redirect politely

CLASSIFICATION CATEGORIES:

1. "YES" → caller confirms payment was made last month
   Examples: "हाँ", "जी हाँ", "हाँ किया था", "yes", "yes I paid"
   Action: NEXT (proceed to next question)
   Response: null

2. "NO" → caller says payment was NOT made last month
   Examples: "नहीं", "नहीं किया", "no", "no I didn't"
   Action: NEXT (proceed to next question - still valid answer)
   Response: null

3. "ROLE_CLARIFICATION" → caller asks about who you are, why calling, etc.
   Action: CLARIFY (provide explanation, then repeat question)
   Response: Generate friendly Hindi explanation of your role, then repeat the payment question

4. "REFUSE" → caller explicitly refuses to participate
   Action: CLOSING (end call gracefully)
   Response: Generate polite closing message in Hindi

5. "OFF_TOPIC" → caller asks about something else
   Action: CLARIFY (acknowledge and redirect)
   Response: Generate polite Hindi response acknowledging their question, then repeat the payment question

6. "UNCLEAR" → reply is too ambiguous or unrelated
   Action: REPEAT (ask question again)
   Response: Generate polite request to repeat the answer in Hindi

Return ONLY this JSON (no extra text):
{
  "value": "YES" | "NO" | "ROLE_CLARIFICATION" | "REFUSE" | "OFF_TOPIC" | "UNCLEAR",
  "is_clear": true | false,
  "action": "NEXT" | "CLARIFY" | "REPEAT" | "CLOSING",
  "response_text": "string or null"
}

CRITICAL GUIDELINES:
- If caller confirms/denies payment → YES/NO, action=NEXT, response_text=null
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
    
    print(f"DEBUG q4_emi_payment LLM response: {r}")
    
    value = r.get("value")
    is_clear = r.get("is_clear", False)
    action = r.get("action", "REPEAT")
    response_text = r.get("response_text")
    
    if not is_clear:
        print(f"DEBUG: LLM returned unclear response for: '{user_input}'")
        if action == "REPEAT" and response_text:
            session["needs_clarification"] = True
            session["clarification_response"] = response_text
            return QuestionResult(True, value="UNCLEAR", extra={"action": action, "response_text": response_text})
        return QuestionResult(False)
    
    print(f"DEBUG: LLM classified '{user_input}' as: {value}, action: {action}")
    
    # Store classification only if YES or NO
    if value in ("YES", "NO"):
        session["last_month_emi_payment"] = value
    
    # Store LLM's decision
    session["llm_action"] = action
    session["llm_response_text"] = response_text
    
    # Handle based on classification
    if value == "ROLE_CLARIFICATION":
        session["needs_role_clarification"] = True
        if response_text:
            session["role_clarification_response"] = response_text
        return QuestionResult(True, value="ROLE_CLARIFICATION", extra={"action": action, "response_text": response_text})
    
    if value == "REFUSE" or action == "CLOSING":
        session["call_should_end"] = True
        if response_text:
            session["closing_message"] = response_text
        return QuestionResult(True, value="REFUSE", extra={"action": action, "response_text": response_text})
    
    if value == "OFF_TOPIC":
        session["needs_clarification"] = True
        if response_text:
            session["clarification_response"] = response_text
        return QuestionResult(True, value="OFF_TOPIC", extra={"action": action, "response_text": response_text})
    
    if value == "UNCLEAR":
        if response_text:
            session["needs_clarification"] = True
            session["clarification_response"] = response_text
        return QuestionResult(True, value="UNCLEAR", extra={"action": action, "response_text": response_text})
    
    # YES or NO - proceed normally
    return QuestionResult(True, value=value, extra={"action": action})
