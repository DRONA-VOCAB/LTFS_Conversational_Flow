from questions.base import QuestionResult
from llm.gemini_client import call_gemini


def get_text():
    return "यह कॉल आपके पर्सनल लोन या टू-व्हीलर लोन के भुगतान अनुभव को समझने के लिए है। क्या आपने एल एंड टी फ़ाइनेंस से लोन लिया है?"


PROMPT = """
        You are an intelligent assistant. Your task is to classify whether the user confirms
        that they have taken a loan from L and T Finance.

        ========================
        CLASSIFICATION RULES
        ========================

        YES → User confirms they have taken a loan.
        Be VERY lenient. Even short or casual confirmations count.

        Devanagari examples (priority):
        "हाँ", "हां", "हाँ जी", "जी हाँ", "हाँ बिल्कुल", "बिल्कुल", "सही है",
        "हाँ मैंने लोन लिया है",
        "हाँ मैंने एल एंड टी फ़ाइनेंस से लोन लिया है",
        "जी, मैंने एल एंड टी फ़ाइनेंस से लोन लिया है"

        Roman / English examples:
        "haa", "haan", "haaa", "ha", "han",
        "yes", "y", "yeah", "yep",
        "haa mene loan liya hai",
        "haan maine L and T Finance se loan liya hai",
        "bilkul", "sahi hai"


        NO → User denies taking a loan or indicates wrong number.

        Devanagari examples (priority):
        "नहीं", "नही", "ना",
        "नहीं मैंने लोन नहीं लिया",
        "मैंने एल एंड टी फ़ाइनेंस से लोन नहीं लिया",
        "गलत नंबर है", "यह गलत नंबर है",
        "माफ़ कीजिए, मैंने कोई लोन नहीं लिया"

        Roman / English examples:
        "nahi", "nhi", "na", "no",
        "nahi maine loan nahi liya",
        "maine L and T Finance se loan nahi liya",
        "wrong number", "galat number hai",
        "wrong number hai maine loan nahi liya"


        UNCLEAR → User is unsure or response is unrelated.

        Examples:
        "याद नहीं आ रहा", "पक्का नहीं कह सकता",
        "शायद", "देखना पड़ेगा",
        "अभी समझ नहीं आ रहा",
        unrelated responses, silence, or noise


        ========================
        IMPORTANT INSTRUCTIONS
        ========================

        - Prefer YES or NO whenever possible
        - Use UNCLEAR only if the response is truly unclear or unrelated
        - Do NOT guess or infer missing intent
        - Do NOT explain your reasoning
        - Do NOT add extra fields
        - Return ONLY valid JSON (no markdown, no text outside JSON)

        ========================
        OUTPUT FORMAT (STRICT)
        ========================

        {
        "value": "YES/NO/UNCLEAR",
        "is_clear": true/false
        }

        Rules:
        - is_clear = true for YES or NO
        - is_clear = false only for UNCLEAR
    """


def handle(user_input, session):
    r = call_gemini(PROMPT + user_input)
    if not r["is_clear"]:
        return QuestionResult(False)
    session["loan_taken"] = r["value"]

    # If user says they didn't take a loan or it's a wrong number, end the call
    if r["value"] == "NO":
        session["call_should_end"] = True

    return QuestionResult(True)
