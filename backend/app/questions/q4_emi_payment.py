from  base import QuestionResult
from  llm.gemini_client import call_gemini


def get_text():
    return "क्या आपने पिछले महीने भुगतान किया था?"


PROMPT = """
You are an intelligent conversational AI assistant for L&T Finance conducting a customer survey call.

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
- "DONT_KNOW" → caller says they don't know/remember/not sure
- "UNCLEAR" → cannot determine from reply

OUT-OF-BOUND HANDLING:
If the caller asks questions NOT related to भुगतान (e.g., "कौन हो आप?", "क्यों कॉल कर रहे हो?", 
asks about loan details, etc.), classify as:
- "ROLE_CLARIFICATION" → asking about who you are, why calling, etc. (cooperative)
- "OFF_TOPIC" → asking about something else - redirect politely

CLASSIFICATION CATEGORIES:

1. "YES" → caller confirms भुगतान was made last month
   Examples: "हाँ", "जी हाँ", "हाँ किया था", "yes", "yes I paid", "हो गया था"
   Action: NEXT (proceed to next question)
   Response: null

2. "NO" → caller says भुगतान was NOT made last month
   Examples: "नहीं", "नहीं किया", "no", "no I didn't", "नहीं हुआ", "मैं भुगतान करना भूल गया/गई था।"
   Action: CLOSING the call gracefully. Generate a polite closing message.
   Response: "धन्यवाद आपके समय के लिए। आपकी फीडबैक हमारे लिए बहुत महत्वपूर्ण है। आपका दिन शुभ हो!""

3. "DONT_KNOW" → caller says they don't know/remember/not sure
   Examples: "पता नहीं", "याद नहीं", "मुझे नहीं पता", "I don't know", "not sure", "याद नहीं है"
   Action: CLARIFY (help them remember gently)
   Response: Generate EMPATHETIC and GENTLE response to help them remember, like:
   - "कृपया याद करने की कोशिश कीजिए, क्या आपने पिछले महीने भुगतान किया था?"
   - "कृपया सोचिए ज़रा, पिछले महीने कोई भुगतान किया था आपने?"
   BE SOFT, EMPATHETIC.

4. "ROLE_CLARIFICATION" → caller asks about who you are, why calling, etc.
   Action: CLARIFY (provide explanation, then repeat question)
   Response: SHORT and DIRECT explanation + repeat question
   Example:
      - "जी, मैं एल एंड टी फाइनेंस से बात कर रही हूँ। हम आपके पेमेंट अनुभव के बारे में जानना चाहते हैं। कृपया बताइए क्या आपने पिछले महीने भुगतान किया था?"

5. "REFUSE" → caller explicitly refuses to participate
   Action: CLOSING (end call gracefully)
   Response: Generate polite closing message in Hindi

6. "OFF_TOPIC" → caller asks about something else
   Action: CLARIFY (acknowledge and redirect)
   Response: Generate polite Hindi response + redirect

7. "UNCLEAR" → reply is too ambiguous or unrelated
   Action: REPEAT (ask question again)
   Response: SOFT response - "मुझे सही से सुनाई नहीं दिया, कृपया कन्फर्म कीजिए पिछले महीने भुगतान हुआ था क्या?"
   NO commanding tone!

Return ONLY this JSON (no extra text):
{
  "value": "YES" | "NO" | "DONT_KNOW" | "ROLE_CLARIFICATION" | "REFUSE" | "OFF_TOPIC" | "UNCLEAR",
  "is_clear": true | false,
  "action": "NEXT" | "CLARIFY" | "REPEAT" | "CLOSING",
  "response_text": "string or null"
}

CRITICAL GUIDELINES:
- If caller confirms/denies भुगतान → YES/NO, action=NEXT, response_text=null
- Strictly ALWAYS return the response_text Devanagari script.
- If caller says "don't know" → DONT_KNOW, action=CLARIFY, generate EMPATHETIC response
- ALWAYS be SOFT and GENTLE when user doesn't remember something
- Use phrases like "कोई बात नहीं", "ठीक है जी", "सोचिए ज़रा" to show empathy
- NEVER sound commanding or rude
- If caller asks about role → ROLE_CLARIFICATION, action=CLARIFY, generate response
- If caller refuses → REFUSE, action=CLOSING, generate closing message
- If caller asks off-topic → OFF_TOPIC, action=CLARIFY, redirect politely
- If unclear → UNCLEAR, action=REPEAT, generate soft clarification request
- All response_text should be in natural, conversational Hindi (Devanagari script)
"""


def handle(user_input, session):
    r = call_gemini(PROMPT + "\n\nUser said: " + user_input)

    # For DONT_KNOW, we ask again empathetically
    if r.get("value") == "DONT_KNOW" and r.get("response_text"):
        return QuestionResult(False, response_text=r.get("response_text"))

    if not r["is_clear"]:
        return QuestionResult(False, response_text=r.get("response_text"))

    session["last_month_emi_भुगतान"] = r["value"]

    # Return response_text for clarifications
    response_text = r.get("response_text")
    action = r.get("action")
    return QuestionResult(
        True, value=r["value"], extra={"response_text": response_text, "action": action}
    )
