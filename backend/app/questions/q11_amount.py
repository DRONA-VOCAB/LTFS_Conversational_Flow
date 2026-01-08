# from questions.base import QuestionResult
# from llm.gemini_client import call_gemini


# def get_text():
#     return "वस्तव में कितना भुगतान किया गया था? कृपया राशि बताइए ताकि हम उसे दर्ज कर सकें."


# PROMPT = """
# You are an intelligent conversational AI assistant for L&T Finance conducting a customer survey call.

# The agent just asked:
# "वास्तव में कितना भुगतान किया गया था? कृपया राशि बताइए ताकि हम उसे दर्ज कर सकें।"

# You receive the caller's reply (in Hindi, Hinglish, or English), which may describe an amount in words or digits.

# Your task is to:
# 1. Understand the caller's intent completely
# 2. Extract payment amount OR handle out-of-bound questions
# 3. Decide what action to take next
# 4. Generate an appropriate response if needed

# MAIN TASK - Extract amount:
# - Extract payment amount as digits only (no commas, no currency symbols)
# - Examples: "पचास हजार" → "50000", "25 हज़ार" → "25000", "10k" → "10000"
# - Ignore currency words like रुपये / rupees / rs / ₹

# OUT-OF-BOUND HANDLING:
# If the caller asks questions NOT related to payment amount (e.g., "कौन हो आप?", "क्यों कॉल कर रहे हो?",
# asks about date, mode, etc.), classify as:
# - "ROLE_CLARIFICATION" → asking about who you are, why calling, etc. (cooperative)
# - "OFF_TOPIC" → asking about something else - redirect politely

# CLASSIFICATION CATEGORIES:

# 1. "ANSWERED" → caller clearly provided payment amount
#    Action: NEXT (proceed to summary)
#    Response: null

# 2. "ROLE_CLARIFICATION" → caller asks about who you are, why calling, etc.
#    Action: CLARIFY (provide explanation, then repeat question)
#    Response: Generate friendly Hindi explanation of your role, then repeat the amount question

# 3. "REFUSE" → caller explicitly refuses to participate
#    Action: CLOSING (end call gracefully)
#    Response: Generate polite closing message in Hindi

# 4. "OFF_TOPIC" → caller asks about something else (date, mode, etc.)
#    Action: CLARIFY (acknowledge and redirect)
#    Response: Generate polite Hindi response acknowledging their question, explaining you'll get to that,
#    and asking the amount question again

# 5. "UNCLEAR" → reply is too ambiguous or unrelated
#    Action: REPEAT (ask question again)
#    Response: Generate polite request to repeat the answer in Hindi

# Return ONLY this JSON (no extra text):
# {
#   "value": "numeric_amount_as_string or null",
#   "classification": "ANSWERED" | "ROLE_CLARIFICATION" | "REFUSE" | "OFF_TOPIC" | "UNCLEAR",
#   "is_clear": true | false,
#   "action": "NEXT" | "CLARIFY" | "REPEAT" | "CLOSING",
#   "response_text": "string or null"
# }

# CRITICAL GUIDELINES:
# - If caller provides amount → ANSWERED, action=NEXT, response_text=null
# - Amount should be digits only (e.g., "50000" not "50,000" or "₹50000")
# - If caller asks about role → ROLE_CLARIFICATION, action=CLARIFY, generate response
# - If caller refuses → REFUSE, action=CLOSING, generate closing message
# - If caller asks off-topic → OFF_TOPIC, action=CLARIFY, redirect politely
# - If unclear → UNCLEAR, action=REPEAT, generate clarification request
# - All response_text should be in natural, conversational Hindi (Devanagari script)
# """


# def handle(user_input, session):
#     r = call_gemini(PROMPT + user_input)
#     if not r["is_clear"]:
#         return QuestionResult(False)
#     session["amount"] = r["value"]
#     return QuestionResult(True)


from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    return "वस्तव में कितना भुगतान किया गया था? कृपया राशि बताइए ताकि हम उसे दर्ज कर सकें."


PROMPT = """
You are an intelligent conversational AI assistant for L&T Finance conducting a customer survey call.

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
   Response: Generate friendly Hindi explanation with acknowledgment + explanation + repeat question

3. "REFUSE" → caller explicitly refuses to participate
   Action: CLOSING (end call gracefully)
   Response: Generate polite closing message in Hindi

4. "OFF_TOPIC" → caller asks about something else (date, mode, etc.)
   Action: CLARIFY (acknowledge and redirect)
   Response: Generate polite Hindi response with acknowledgment + redirect + repeat question

5. "UNCLEAR" → reply is too ambiguous or unrelated
   Action: REPEAT (ask question again with acknowledgment)
   Response: Generate acknowledgment of what they said + polite request for amount
   Example responses:
   - "जी, मैं समझा... लेकिन राशि स्पष्ट नहीं हुई। कृपया बताइए कितना payment किया था?"
   - "अच्छा जी... तो exact amount क्या थी? कितने रुपये का भुगतान किया था?"
   - "हाँ जी... लेकिन मुझे amount confirm करनी है। कितनी रकम payment की थी आपने?"

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
- Strictly ALWAYS return the response_text Devanagari script.
- Amount should be digits only (e.g., "50000" not "50,000" or "₹50000")
- ALWAYS include conversational acknowledgments in response_text (जी, अच्छा, हाँ जी, बिल्कुल, etc.)
- For UNCLEAR: acknowledge that you heard them, then politely ask for the amount again
- Make responses sound natural and interactive, not robotic
- Vary the acknowledgment phrases to avoid repetition
- If caller asks about role → ROLE_CLARIFICATION, action=CLARIFY, generate response
- If caller refuses → REFUSE, action=CLOSING, generate closing message
- If caller asks off-topic → OFF_TOPIC, action=CLARIFY, redirect politely
- All response_text should be in natural, conversational Hindi (Devanagari script)
"""


def handle(user_input, session):
    r = call_gemini(PROMPT + "\n\nUser said: " + user_input)

    if not r["is_clear"]:
        return QuestionResult(False, response_text=r.get("response_text"))

    session["amount"] = r["value"]

    # Return response_text for clarifications
    response_text = r.get("response_text")
    return QuestionResult(
        True, value=r["value"], extra={"response_text": response_text}
    )
