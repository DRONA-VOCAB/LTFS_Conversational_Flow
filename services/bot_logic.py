from services.greeting import get_greeting
from services.identity import get_customer_by_id
from services.session import sessions

YES_WORDS = {"yes", "yeah", "yep", "haan", "ji", "speaking"}
NO_WORDS = {"no", "not me", "wrong person"}

RELATIVE_WORDS = {"father", "mother", "brother", "sister", "wife", "husband", "relative"}
NOT_AVAILABLE_WORDS = {"not available", "busy", "call later", "not now"}

ABRUPT_WORDS = {"why", "who", "what", "huh", "?", "dont know", "no idea", "maybe"}


def start_conversation(customer_id: int, session_id: str):
    greeting = get_greeting()

    customer = get_customer_by_id(customer_id)
    if not customer:
        return "Sorry, we could not find your details. Ending the call."

    _, customer_name = customer

    sessions[session_id] = {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "state": "ASK_IDENTITY",
        "deny_count": 0
    }

    return (
        f"{greeting}! Hi, I am calling from LTFS.\n"
        f"Am I speaking to {customer_name}?"
    )


import re

def handle_identity_reply(user_input: str, session_id: str):
    session = sessions.get(session_id)

    if not session:
        return "Session expired. Please call again."

    # ---------- SAFE DEFAULTS ----------
    session.setdefault("deny_count", 0)
    session.setdefault("invalid_count", 0)
    session.setdefault("availability", None)
    session.setdefault("callback_time", None)

    answer = user_input.lower().strip()

    # ---------- intent detection ----------
    is_yes = any(word in answer for word in YES_WORDS)
    is_no = any(word in answer for word in NO_WORDS)
    is_busy = any(word in answer for word in NOT_AVAILABLE_WORDS)
    is_relative = any(word in answer for word in RELATIVE_WORDS)

    # =========================
    # STATE: ASK_IDENTITY
    # =========================
    if session["state"] == "ASK_IDENTITY":

        # YES but BUSY
        if is_yes and is_busy:
            session["availability"] = "busy"
            session["state"] = "ASK_CALLBACK_TIME"
            return "I understand. May I know a convenient time to call back?"

        # YES (confirmed)
        if is_yes:
            session["state"] = "CONFIRMED"
            return (
                f"Thank you {session['customer_name']}.\n"
                "This is a survey call. I would like to ask you some questions."
            )

        # NO (denied)
        if is_no:
            session["deny_count"] += 1
            if session["deny_count"] == 1:
                return f"Sorry about that. Am I speaking to {session['customer_name']}?"
            session["state"] = "END"
            session["end_reason"] = "identity_denied"
            return "We could not verify your identity. Ending the call."

        # RELATIVE
        if is_relative:
            session["state"] = "ASK_AVAILABILITY"
            return (
                f"Thank you for informing.\n"
                f"Is {session['customer_name']} available to speak right now?"
            )

    # =========================
    # STATE: CONFIRMED
    # =========================
    if session["state"] == "CONFIRMED":

        if is_busy:
            session["availability"] = "busy"
            session["state"] = "ASK_CALLBACK_TIME"
            return "No problem. May I know a convenient time to call back?"

        return "Shall we proceed with the survey?"

    # =========================
    # STATE: ASK_AVAILABILITY
    # =========================
    if session["state"] == "ASK_AVAILABILITY":

        if is_yes:
            session["availability"] = "available"
            session["state"] = "ASK_IDENTITY"
            return f"Thank you. May I please speak to {session['customer_name']}?"

        if is_no or is_busy:
            session["availability"] = "busy"
            session["state"] = "ASK_CALLBACK_TIME"
            return "May I know a convenient time to call back?"

    # =========================
    # STATE: ASK_CALLBACK_TIME
    # =========================
    if session["state"] == "ASK_CALLBACK_TIME":

        # 🔑 Extract first integer from input
        match = re.search(r"\b\d+\b", user_input)

        if not match:
            return "Please tell me a valid time in hours, like 9 or 5."

        callback_hour = int(match.group())

        session["callback_time"] = callback_hour
        session["state"] = "END"
        session["end_reason"] = "callback_scheduled"

        return (
            f"Thank you. We will call back at {callback_hour}.\n"
            "Have a good day."
        )

    # =========================
    # INVALID / ABRUPT HANDLING
    # =========================
    session["invalid_count"] += 1

    if session["invalid_count"] <= 2:
        return "Please reply clearly so that I can assist you."

    session["state"] = "END"
    session["end_reason"] = "invalid_response"
    return "We are unable to proceed due to unclear responses. Ending the call."
