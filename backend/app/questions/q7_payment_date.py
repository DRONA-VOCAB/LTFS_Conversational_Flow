from  base import QuestionResult
from  llm.gemini_client import call_gemini


def get_text():
    return "आपने भुगतान किस तारीख पर किया था?"


PROMPT = """
You are an intelligent conversational AI assistant for L&T Finance conducting a customer survey call.

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

2. "PARTIAL_DATE" → caller provided partial information (date range, approximate time, only month, etc.)
   Examples: "7 या 8 तारीख", "महीने के शुरू में", "दिसंबर में कभी", "around 5th", "first week"
   Action: CLARIFY (acknowledge partial info, ask for exact date)
   Response: Generate acknowledgment of what they said + polite request for exact date
   Example responses:
   - "अच्छा जी, 7 या 8 तारीख के आसपास... धन्यवाद बताने के लिए। लेकिन क्या आप exact तारीख बता सकते हैं? 7 थी या 8?"
   - "जी समझा, दिसंबर में... लेकिन दिसंबर की कौन सी तारीख थी? अगर आपको याद हो तो बताइए।"
   - "हाँ जी, महीने के शुरू में... क्या आप exact date बता सकते हैं?"

3. "ROLE_CLARIFICATION" → caller asks about who you are, why calling, etc.
   Action: CLARIFY (provide explanation, then repeat question)
   Response: Generate friendly Hindi explanation with acknowledgment + explanation + repeat question

4. "REFUSE" → caller explicitly refuses to participate
   Action: CLOSING (end call gracefully)
   Response: Generate polite closing message in Hindi

5. "OFF_TOPIC" → caller asks about something else (amount, mode, etc.)
   Action: CLARIFY (acknowledge and redirect)
   Response: Generate polite Hindi response with acknowledgment + redirect + repeat question

6. "UNCLEAR" → reply is too ambiguous or unrelated
   Action: REPEAT (ask question again with acknowledgment)
   Response: Generate acknowledgment of what they said (if anything) + polite request to repeat
   Example responses:
   - "मैं समझ गई हूँ कि आपने भुगतान लगभग दो हफ्ते पहले किया था, लेकिन क्या आप कृपया पक्की तारीख बता सकते हैं ताकि हम उसे दर्ज कर सकें?"
   - "जी तारीख स्पष्ट नहीं हुई। कृपया बताइए कि आपने किस तारीख को भुगतान किया था?"
   - "जी मैं समझ गई हूँ कि आपने भुगतान किया था, लेकिन क्या आप कृपया पक्की तारीख बता सकते हैं ताकि हम उसे दर्ज कर सकें?"

Return ONLY this JSON (no extra text):
{
  "value": "dd/mm/yyyy or null",
  "classification": "ANSWERED" | "PARTIAL_DATE" | "ROLE_CLARIFICATION" | "REFUSE" | "OFF_TOPIC" | "UNCLEAR",
  "is_clear": true | false,
  "action": "NEXT" | "CLARIFY" | "REPEAT" | "CLOSING",
  "response_text": "string or null",
  "user_said": "brief summary of what user mentioned (for acknowledgment)"
}

CRITICAL GUIDELINES:
- If caller provides EXACT date OR says "don't know" → ANSWERED, action=NEXT, response_text=null
- Strictly ALWAYS return the response_text Devanagari script.
- If caller provides PARTIAL/RANGE/APPROXIMATE date → PARTIAL_DATE, action=CLARIFY, generate acknowledgment + request exact date
- Date must be in dd/mm/yyyy format if provided
- ALWAYS include conversational acknowledgments in response_text (जी, अच्छा, हाँ जी, धन्यवाद, etc.)
- For PARTIAL_DATE: acknowledge what they said, thank them, then ask for exact date in a friendly way
- For UNCLEAR: acknowledge that you heard them, then politely ask for the date again
- Make responses sound natural and interactive, not robotic
- Vary the acknowledgment phrases to avoid repetition
- If caller asks about role → ROLE_CLARIFICATION, action=CLARIFY, generate response
- If caller refuses → REFUSE, action=CLOSING, generate closing message
- If caller asks off-topic → OFF_TOPIC, action=CLARIFY, redirect politely
- All response_text should be in natural, conversational Hindi (Devanagari script)
"""


def handle(user_input, session):
    r = call_gemini(PROMPT + "\n\nUser said: " + user_input)

    # For PARTIAL_DATE or UNCLEAR, we need to ask again with acknowledgment
    if r.get("classification") in ["PARTIAL_DATE", "UNCLEAR"] and r.get(
        "response_text"
    ):
        return QuestionResult(False, response_text=r.get("response_text"))

    if not r["is_clear"]:
        return QuestionResult(False, response_text=r.get("response_text"))

    session["pay_date"] = r["value"]

    # Return response_text for clarifications
    response_text = r.get("response_text")
    action = r.get("action")
    return QuestionResult(
        True, value=r["value"], extra={"response_text": response_text, "action": action}
    )
