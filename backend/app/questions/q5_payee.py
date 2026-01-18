from  base import QuestionResult
from  llm.gemini_client import call_gemini


def get_text():
    return "यह भुगतान किसने किया था? आपने खुद या किसी और ने?"


PROMPT = """
        You are an intelligent assistant.

        Question asked to the user:
        "यह भुगतान किसने किया था — आपने खुद या किसी और ने?"

        Your task is to determine WHO made the payment based on the user's response.

        ========================
        AVAILABLE OPTIONS
        ========================

        1. self          → User says they paid themselves
        2. relative      → Payment made by a family member
        3. friend        → Payment made by a friend
        4. third_party   → Payment made by someone else (agent, office, unknown person, etc.)

        ========================
        CLASSIFICATION RULES
        ========================

        SELF → User confirms they paid themselves.

        Devanagari examples (priority):
        "मैंने खुद किया",
        "मैंने भुगतान किया",
        "मैंने ही पेमेंट किया",
        "मेरे द्वारा किया गया था",
        "मैंने अपनी तरफ से किया"

        Roman examples:
        "main khud kiya",
        "maine payment kiya",
        "maine hi pay kiya",
        "self kiya"


        RELATIVE → Payment made by a family member
        (father, mother, brother, sister, husband, wife, son, daughter, etc.)

        Devanagari examples (priority):
        "मेरे पापा ने किया",
        "मम्मी ने पेमेंट किया",
        "मेरे भाई ने किया",
        "मेरी बहन ने किया",
        "पति ने किया",
        "पत्नी ने किया",
        "घर वालों ने किया"

        Roman examples:
        "mere papa ne kiya",
        "meri mummy ne payment kiya",
        "bhai ne kiya",
        "behen ne kiya",
        "ghar wale ne kiya"


        FRIEND → Payment made by a friend.

        Devanagari examples (priority):
        "मेरे दोस्त ने किया",
        "मित्र ने भुगतान किया",
        "एक दोस्त ने किया"

        Roman examples:
        "mere dost ne kiya",
        "friend ne payment kiya",
        "ek friend ne kiya"


        THIRD_PARTY → Payment made by someone else or an unspecified person
        (office, agent, company, shop, unknown person, etc.)

        Devanagari examples (priority):
        "किसी और ने किया",
        "ऑफिस से किया गया",
        "एजेंट ने किया",
        "कंपनी की तरफ से हुआ",
        "मुझे नहीं पता किसने किया"

        Roman examples:
        "kisi aur ne kiya",
        "office se kiya",
        "agent ne kiya",
        "company ne kiya",
        "pata nahi kisne kiya"


        ========================
        UNCLEAR CASES
        ========================

        If the response:
        - Does not mention who made the payment
        - Is ambiguous or unrelated
        - Only repeats the question
        - Is noise / silence

        Then classify as UNCLEAR.

        Examples:
        "पता नहीं",
        "याद नहीं है",
        "समझ नहीं आया",
        unrelated responses or noise

        ========================
        IMPORTANT INSTRUCTIONS
        ========================

        - Choose the BEST matching option
        - Do NOT guess if unclear
        - If a family member is mentioned → relative
        - If friend is mentioned → friend
        - If clearly self → self
        - If someone else or unknown → third_party
        - Do NOT explain your reasoning
        - Do NOT add extra fields
        - Return ONLY valid JSON

        ========================
        OUTPUT FORMAT (STRICT)
        ========================

        {
        "value": "self/relative/friend/third_party",
        "is_clear": true/false
        }

        Rules:
        - is_clear = true if value is one of the four options
        - is_clear = false ONLY if truly unclear
    """


def handle(user_input, session):
    r = call_gemini(PROMPT + user_input)
    if not r["is_clear"]:
        return QuestionResult(False)
    session["payee"] = r["value"]
    return QuestionResult(True)
