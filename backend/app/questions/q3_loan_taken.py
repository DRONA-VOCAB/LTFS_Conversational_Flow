from app.questions.base import QuestionResult
from app.llm.gemini_client import call_gemini
from app.config.settings import COMPANY_NAME_FORMAL, get_message


def get_text():
    return "यह कॉल आपके लोन के भुगतान अनुभव को समझने के लिए है। क्या आपने एल एंड टी फ़ाइनेंस से लोन लिया है?"


def _get_prompt_template():
    """Get the prompt template with dynamic company name"""
    return f"""
You are an intelligent conversational AI assistant for {COMPANY_NAME_FORMAL} conducting a customer survey call.

The agent just asked:
"यह कॉल आपके लोन के भुगतान अनुभव को समझने के लिए है। क्या आपने एल एंड टी फ़ाइनेंस से लोन लिया है?"

You receive the caller's reply (in Hindi, Hinglish, or English).

Your task is to:
1. Understand the caller's intent completely
2. Classify the response OR handle out-of-bound questions
3. Decide what action to take next
4. Generate an appropriate response if needed

MAIN CLASSIFICATION:
- "YES" → caller clearly confirms they have taken a loan from L&T Finance
- "NO" → caller clearly says they have NOT taken such a loan, or wrong number
- "REFUSE" → caller refuses to participate or cooperate

OUT-OF-BOUND HANDLING:
If the caller asks questions NOT related to loan (e.g., "कौन हो आप?", "क्यों कॉल कर रहे हो?", 
asks about payment details, etc.), classify as:
- "ROLE_CLARIFICATION" → asking about who you are, why calling, etc. (cooperative)
- "OFF_TOPIC" → asking about something else (payment, other details) - redirect politely

CLASSIFICATION CATEGORIES:

1. "YES" → caller confirms they have a loan from L&T Finance
   Examples: "हाँ", "जी हाँ", "हाँ लिया है", "yes", "yes I have"
   Action: NEXT (proceed to next question)
   Response: null

2. "NO" → caller says they don't have a loan or wrong number
   Examples: "नहीं", "गलत नंबर", "मैंने लोन नहीं लिया", "no", "wrong number"
   Action: CLOSING (end call - no loan means survey doesn't apply)
   Response: Generate APOLOGY message in Hindi (use appropriate apology message for wrong number)
   IMPORTANT: Must include apology, NOT "thank you for confirming callback time"

3. "ROLE_CLARIFICATION" → caller asks about who you are, why calling, etc.
   Action: CLARIFY (provide explanation, then repeat question)
   Response: Generate friendly Hindi explanation of your role, then repeat the loan question

4. "REFUSE" → caller explicitly refuses to participate
   Examples: "मुझे बात नहीं करनी", "कॉल मत करो", "I don't want to talk"
   Action: CLOSING (end call gracefully)
   Response: Generate polite closing message in Hindi

5. "OFF_TOPIC" → caller asks about something else (payment, other details)
   Action: CLARIFY (acknowledge and redirect)
   Response: Generate polite Hindi response explaining you'll get to payment questions after 
   confirming the loan, then repeat the loan question

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
- If caller confirms loan → YES, action=NEXT, response_text=null
- If caller denies loan → NO, action=CLOSING, generate closing message
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
    
    print(f"DEBUG q3_loan_taken LLM response: {r}")
    
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
    
    # Store classification
    session["loan_taken"] = value
    
    # Store LLM's decision
    session["llm_action"] = action
    session["llm_response_text"] = response_text
    
    # Handle based on classification
    if value == "ROLE_CLARIFICATION":
        session["needs_role_clarification"] = True
        if response_text:
            session["role_clarification_response"] = response_text
        return QuestionResult(True, value="ROLE_CLARIFICATION", extra={"action": action, "response_text": response_text})
    
    if value == "NO":
        session["call_should_end"] = True
        if response_text:
            session["closing_message"] = response_text
        else:
            # Default apology message for no loan
            session["closing_message"] = get_message("wrong_number_apology")
        return QuestionResult(True, value=value, extra={"action": "CLOSING", "response_text": session["closing_message"]})
    
    if value == "REFUSE" or action == "CLOSING":
        session["call_should_end"] = True
        if response_text:
            session["closing_message"] = response_text
        return QuestionResult(True, value=value, extra={"action": action, "response_text": response_text})
    
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
    
    # YES - proceed normally
    return QuestionResult(True, value=value, extra={"action": action})
