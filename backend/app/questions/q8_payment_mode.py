from  base import QuestionResult
from  llm.gemini_client import call_gemini


def get_text():
    return "कृपया बताइए—आपने भुगतान किस माध्यम से किया था… ऑनलाइन.. जैसे यूपीआई, .. एनईएफ़टी या आरटीजीएस से… फ़ील्ड एग्ज़ीक्यूटिव को .. ऑनलाइन या यूपीआई द्वारा… नकद में… शाखा या आउटलेट पर जाकर… या फिर एनएसीएच के माध्यम से?"


PROMPT = """
You are an intelligent conversational AI assistant for L&T Finance conducting a customer survey call.

The agent just asked:
"कृपया बताइए, आपने भुगतान किस माध्यम से किया था—क्या यह ऑनलाइन जैसे UPI, NEFT या RTGS से, फ़ील्ड एग्ज़ीक्यूटिव को ऑनलाइन या UPI द्वारा, नकद में, शाखा या आउटलेट पर जाकर, या फिर NACH के माध्यम से किया गया था?"

You receive the caller's reply (in Hindi, Hinglish, or English).

Your task is to:
1. Understand the caller's intent completely
2. Extract payment mode OR handle out-of-bound questions
3. Decide what action to take next
4. Generate an appropriate response if needed

MAIN TASK - Extract payment mode:
Map to one of: "online_lan", "online_field_executive", "cash", "branch", "outlet", "nach"

IMPORTANT PAYMENT MODE MAPPINGS:
- "auto-debit", "auto debit", "automatic", "NACH", "auto", "ऑटो डेबिट", "स्वचालित" → "nach"
- "online", "UPI", "netbanking", "ऑनलाइन", "यूपीआई" → "online_lan"
- "cash", "नगद", "cash in hand" → "cash"
- "branch", "बैंक", "शाखा" → "branch"

OUT-OF-BOUND HANDLING:
If the caller asks questions NOT related to payment mode (e.g., "कौन हो आप?", "क्यों कॉल कर रहे हो?", 
asks about amount, date, etc.), classify as:
- "ROLE_CLARIFICATION" → asking about who you are, why calling, etc. (cooperative)
- "OFF_TOPIC" → asking about something else - redirect politely

CLASSIFICATION CATEGORIES:

1. "ANSWERED" → caller clearly indicates payment mode
   Examples: "ऑनलाइन", "यूपीआई", "नगद", "cash", "online", "branch"
   Action: NEXT (proceed to next question)
   Response: null

2. "ROLE_CLARIFICATION" → caller asks about who you are, why calling, etc.
   Action: CLARIFY (provide explanation, then repeat question)
   Response: Generate friendly Hindi explanation with acknowledgment + explanation + repeat question

3. "REFUSE" → caller explicitly refuses to participate
   Action: CLOSING (end call gracefully)
   Response: Generate polite closing message in Hindi

4. "OFF_TOPIC" → caller asks about something else (amount, date, etc.)
   Action: CLARIFY (acknowledge and redirect)
   Response: Generate polite Hindi response with acknowledgment + redirect + repeat question

5. "UNCLEAR" → reply is too ambiguous or unrelated
   Action: REPEAT (ask question again with acknowledgment)
   Response: Generate acknowledgment + polite request to repeat

Return ONLY this JSON (no extra text):
{
  "value": "online_lan" | "online_field_executive" | "cash" | "branch" | "outlet" | "nach" | "ROLE_CLARIFICATION" | "REFUSE" | "OFF_TOPIC" | "UNCLEAR",
  "is_clear": true | false,
  "action": "NEXT" | "CLARIFY" | "REPEAT" | "CLOSING",
  "response_text": "string or null"
}

CRITICAL GUIDELINES:
- If caller indicates payment mode → ANSWERED (one of the modes), action=NEXT, response_text=null
- Strictly ALWAYS return the response_text Devanagari script.
- ALWAYS include conversational acknowledgments in response_text (जी, अच्छा, हाँ जी, बिल्कुल, etc.)
- Make responses sound natural and interactive, not robotic
- If caller asks about role → ROLE_CLARIFICATION, action=CLARIFY, generate response
- If caller refuses → REFUSE, action=CLOSING, generate closing message
- If caller asks off-topic → OFF_TOPIC, action=CLARIFY, redirect politely
- If unclear → UNCLEAR, action=REPEAT, generate clarification request
- All response_text should be in natural, conversational Hindi (Devanagari script)
"""


def handle(user_input, session):
    r = call_gemini(PROMPT + "\n\nUser said: " + user_input)

    if not r["is_clear"]:
        return QuestionResult(False, response_text=r.get("response_text"))

    # r["value"] is a STRING, not a dict!
    # It's one of: "online_lan", "cash", "branch", etc.
    session["mode_of_payment"] = r["value"]

    # Return response_text for clarifications
    response_text = r.get("response_text")
    action = r.get("action")
    return QuestionResult(
        True, value=r["value"], extra={"response_text": response_text, "action": action}
    )
