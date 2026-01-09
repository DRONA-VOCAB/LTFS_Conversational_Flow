from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    return "यह कॉल आपके {{product_type}} के भुगतान अनुभव को समझने के लिए है। क्या आपने एल एंड टी फ़ाइनेंस से लोन लिया है?"


PROMPT = """
You are an intelligent conversational AI assistant for L&T Finance conducting a customer survey call.

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
   Response: Generate APOLOGY message in Hindi: "जी, माफ़ कीजिए, लगता है हमने गलत नंबर पर कॉल कर लिया है। आपके समय के लिए धन्यवाद। आपका दिन शुभ हो।"
   IMPORTANT: Must include apology, NOT "thank you for confirming callback time"

3. "ROLE_CLARIFICATION" → caller asks about who you are, why calling, etc.
   Action: CLARIFY (provide explanation, then repeat question)
   Response: Generate friendly Hindi explanation with acknowledgment + explanation + repeat question
   Example: "जी बिल्कुल, मैं L&T Finance की तरफ से बात कर रही हूँ। हम अपने customers के payment experience के बारे में जानना चाहते हैं। तो क्या आपने L&T Finance से लोन लिया है?"

4. "REFUSE" → caller explicitly refuses to participate
   Examples: "मुझे बात नहीं करनी", "कॉल मत करो", "I don't want to talk"
   Action: CLOSING (end call gracefully)
   Response: Generate polite closing message with acknowledgment: "जी समझा। कोई बात नहीं। आपके समय के लिए धन्यवाद। आपका दिन शुभ हो!"

5. "OFF_TOPIC" → caller asks about something else (payment, other details)
   Action: CLARIFY (acknowledge and redirect)
   Response: Generate polite Hindi response with acknowledgment + redirect + repeat question
   Example: "अच्छा जी, वो सब details मैं आगे पूछूंगी। पहले मुझे confirm करना है - क्या आपने L&T Finance से loan लिया है?"

6. "UNCLEAR" → reply is too ambiguous or unrelated
   Action: REPEAT (ask question again with acknowledgment)
   Response: Generate acknowledgment + polite request to repeat
   Examples: 
   - "मुझे सही से सुनाई नहीं दिया, कृपया कन्फर्म कीजिए क्या आपने L&T Finance से लोन लिया है?"
   - "मुझे ठीक से समझ नहीं आया। क्या आप दोबारा बता सकते हैं कि क्या आपने एल एंड टी फाइनेंस से लोन लिया है?"

Return ONLY this JSON (no extra text):
{
  "value": "YES" | "NO" | "ROLE_CLARIFICATION" | "REFUSE" | "OFF_TOPIC" | "UNCLEAR",
  "is_clear": true | false,
  "action": "NEXT" | "CLARIFY" | "REPEAT" | "CLOSING",
  "response_text": "string or null" 
}

CRITICAL GUIDELINES:
- If caller confirms loan → YES, action=NEXT, response_text=null
- Strictly ALWAYS return the response_text Devanagari script.
- If caller denies loan → NO, action=CLOSING, generate closing message
- ALWAYS include conversational acknowledgments (जी, अच्छा, हाँ जी, बिल्कुल, समझा, etc.)
- Make responses sound natural and interactive, not robotic
- Vary the acknowledgment phrases to avoid repetition
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

    session["loan_taken"] = r["value"]

    # If user says they didn't take a loan or it's a wrong number, end the call
    if r["value"] == "NO":
        session["call_should_end"] = True

    # Return response_text for clarifications
    response_text = r.get("response_text")
    action = r.get("action")
    return QuestionResult(
        True, value=r["value"], extra={"response_text": response_text, "action": action}
    )
