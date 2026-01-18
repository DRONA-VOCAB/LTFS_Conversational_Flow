from  base import QuestionResult
from  llm.gemini_client import call_gemini


def get_text():
    return "आपने भुगतान किस तारीख पर किया था?"


PROMPT = """
        You are an intelligent assistant. The current year is 2025.

        Question asked to the user:
        "आपने पेमेंट किस तारीख को किया था?"

        Your task is to extract the DATE of payment from the user's response and return it
        in **dd/mm/yyyy** format.

        ========================
        DATE EXTRACTION RULES
        ========================

        - Extract any date mentioned by the user.
        - Date may be expressed as:
        - Day + Month (spoken or written)
        - Numeric dates
        - Relative phrases (convert if clear)

        - Month names may be in Hindi, English, or Hinglish.
        - IMPORTANT: The YEAR must be either **2025 or 2026** only.
        - If the year is not explicitly mentioned, use 2025 as the default year.
        - Only use 2026 if the user clearly indicates a future date.
        - NEVER use years like 2024, 2023, or any year before 2025.

        ========================
        EXAMPLES (DEVANAGARI FIRST)
        ========================

        "3 दिसंबर को किया था"
        → value: "03/12/2025"

        "तीन दिसंबर को पेमेंट किया"
        → value: "03/12/2025"

        "15 जनवरी को किया था"
        → value: "15/01/2025" (default to 2025)

        "कल किया था" (if clearly refers to a known previous date in context)
        → extract date accordingly, else UNCLEAR

        "पिछले महीने 10 तारीख को किया"
        → value: "10/<previous_month>/2025" (only if month can be inferred, else UNCLEAR)


        Roman examples:
        "december 3 ko kiya tha"
        → value: "03/12/2025"

        "3 dec ko payment kiya"
        → value: "03/12/2025"

        "15 jan ko kiya tha"
        → value: "15/01/2025"

        "05/12/2025"
        → value: "05/12/2025"

        "5-12-25"
        → value: "05/12/2025"


        ========================
        UNCLEAR CASES
        ========================

        Mark as UNCLEAR if:
        - No date is mentioned
        - Date is too vague to infer
        - Response is unrelated or unclear

        Examples:
        "याद नहीं है",
        "पता नहीं",
        "अभी नहीं किया",
        unrelated responses or noise

        → value = null
        → is_clear = false

        ========================
        IMPORTANT INSTRUCTIONS
        ========================

        - Return date strictly in **dd/mm/yyyy** format
        - ALWAYS use 2025 as the year unless explicitly told otherwise
        - Do NOT use 2024, 2023, or any year before 2025
        - Do NOT guess if date cannot be reasonably inferred
        - If date is clearly extracted → is_clear = true
        - If date is missing or unclear → is_clear = false
        - Do NOT explain your reasoning
        - Do NOT add extra fields
        - Return ONLY valid JSON (no markdown, no text outside JSON)

        ========================
        OUTPUT FORMAT (STRICT)
        ========================

        {
        "value": "dd/mm/yyyy",
        "is_clear": true/false
        }
    """


def handle(user_input, session):
    r = call_gemini(PROMPT + user_input)
    if not r["is_clear"]:
        return QuestionResult(False)
    session["pay_date"] = r["value"]
    return QuestionResult(True)
