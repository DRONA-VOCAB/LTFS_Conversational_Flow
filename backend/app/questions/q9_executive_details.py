from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    return "क्या आप मुझे फील्ड एग्ज़ीक्यूटिव का नाम और नंबर बता सकते हैं?"

    
PROMPT = """
You are an intelligent conversational AI assistant for L&T Finance conducting a customer survey call.

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
- Strictly ALWAYS return the response_text Devanagari script.
- If caller asks about role → ROLE_CLARIFICATION, action=CLARIFY, generate response
- If caller refuses → REFUSE, action=CLOSING, generate closing message
- If caller asks off-topic → OFF_TOPIC, action=CLARIFY, redirect politely
- If unclear → UNCLEAR, action=REPEAT, generate clarification request
- All response_text should be in natural, conversational Hindi (Devanagari script)
"""



def handle(user_input, session):
    r = call_gemini(PROMPT + user_input)
    if not r["is_clear"]:
        return QuestionResult(False)
    if r["value"].get("field_executive_name"):
        session["field_executive_name"] = r["value"].get("field_executive_name")
    if r["value"].get("field_executive_contact"):
        session["field_executive_contact"] = r["value"].get("field_executive_contact")
    return QuestionResult(True, value=r["value"], extra={"response_text": r.get("response_text"), "action": r.get("action")})

