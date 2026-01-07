from app.questions.base import QuestionResult
from app.llm.gemini_client import call_gemini
from app.config.settings import COMPANY_NAME_FORMAL


def get_text():
    return "आपने भुगतान किस तारीख पर किया था?"


def _get_prompt_template():
    """Get the prompt template with dynamic company name"""
    return f"""
You are an intelligent conversational AI assistant for {COMPANY_NAME_FORMAL} conducting a customer survey call.

The agent just asked:
"आपने भुगतान किस तारीख पर किया था?"

You receive the caller's reply (in Hindi, Hinglish, or English).

Your task is to:
1. Understand the caller's intent completely
2. Extract payment date OR handle out-of-bound questions
3. Decide what action to take next
4. Generate an appropriate response if needed

MAIN TASK - Extract date:
- Extract payment date in dd/mm/yyyy format
- If caller says "don't know" or "not remembered", accept as valid (value=null, is_clear=true)

DATE EXTRACTION RULES:
- Extract any clear date mentioned (day + month + year)
- Month names may be in Hindi, English, or Hinglish
- Year should be 2025 or 2026 (default to 2025 if not mentioned)
- Convert relative dates only if exact calendar date is clear
- Examples: "3 दिसंबर" → "03/12/2025", "15 जनवरी" → "15/01/2026", "das taareekh" → "10/<month>/2025"
- IMPORTANT: If caller says "7 or 8" or multiple dates, extract the FIRST/MOST RECENT date mentioned
- If only day mentioned (e.g., "das" = 10), try to infer month from context, else ask for clarification
- Handle partial dates: "das taareekh" means 10th of some month - extract as "10/<inferred_month>/2025" if possible

OUT-OF-BOUND HANDLING:
If the caller asks questions NOT related to payment date (e.g., "कौन हो आप?", "क्यों कॉल कर रहे हो?", 
asks about amount, mode, etc.), classify as:
- "ROLE_CLARIFICATION" → asking about who you are, why calling, etc. (cooperative)
- "OFF_TOPIC" → asking about something else - redirect politely

CLASSIFICATION CATEGORIES:

1. "ANSWERED" → caller provided date OR said they don't know/remember
   Action: NEXT (proceed to next question)
   Response: null

2. "ROLE_CLARIFICATION" → caller asks about who you are, why calling, etc.
   Action: CLARIFY (provide explanation, then repeat question)
   Response: Generate friendly Hindi explanation of your role, then repeat the date question

3. "REFUSE" → caller explicitly refuses to participate
   Action: CLOSING (end call gracefully)
   Response: Generate polite closing message in Hindi

4. "OFF_TOPIC" → caller asks about something else (amount, mode, etc.)
   Action: CLARIFY (acknowledge and redirect)
   Response: Generate polite Hindi response acknowledging their question, explaining you'll get to that, 
   and asking the date question again

5. "UNCLEAR" → reply is too ambiguous or unrelated
   Action: REPEAT (ask question again)
   Response: Generate polite request to repeat the answer in Hindi

Return ONLY this JSON (no extra text):
{
  "value": "dd/mm/yyyy or null",
  "classification": "ANSWERED" | "ROLE_CLARIFICATION" | "REFUSE" | "OFF_TOPIC" | "UNCLEAR",
  "is_clear": true | false,
  "action": "NEXT" | "CLARIFY" | "REPEAT" | "CLOSING",
  "response_text": "string or null"
}

CRITICAL GUIDELINES:
- If caller provides date OR says "don't know" → ANSWERED, action=NEXT, response_text=null
- Date must be in dd/mm/yyyy format if provided
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
    
    print(f"DEBUG q7_payment_date LLM response: {r}")
    
    classification = r.get("classification", "UNCLEAR")
    is_clear = r.get("is_clear", False)
    action = r.get("action", "REPEAT")
    response_text = r.get("response_text")
    value = r.get("value")
    
    # Store LLM's decision
    session["llm_action"] = action
    session["llm_response_text"] = response_text
    
    # Handle out-of-bound cases first
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
        if not is_clear:
            if response_text:
                session["needs_clarification"] = True
                session["clarification_response"] = response_text
            return QuestionResult(True, value="UNCLEAR", extra={"action": action, "response_text": response_text})
        return QuestionResult(False)
    
    # ANSWERED - validate and store date
    if classification == "ANSWERED":
        # If customer clearly doesn't know, accept null
        if value in (None, "", "null"):
            session["pay_date"] = None
            return QuestionResult(True, value="ANSWERED", extra={"action": action})
        
        # Validate date format
        from datetime import datetime
        try:
            parsed = datetime.strptime(value, "%d/%m/%Y")
            session["pay_date"] = parsed.strftime("%d/%m/%Y")
            return QuestionResult(True, value="ANSWERED", extra={"action": action})
        except Exception:
            # Invalid date format - treat as unclear
            if response_text:
                session["needs_clarification"] = True
                session["clarification_response"] = response_text or "कृपया तारीख स्पष्ट रूप से बताइए, जैसे 3 दिसंबर या 15 जनवरी।"
            return QuestionResult(False)
    
    return QuestionResult(False)
