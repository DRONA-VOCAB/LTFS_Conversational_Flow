"""Service for generating summaries and closing statements"""

from flow.flow_manager import get_next_question_index
from flow.question_order import QUESTIONS
from llm.gemini_client import model


def generate_human_summary(session: dict) -> str:
    """Generate a human-readable summary from session data using LLM"""
    # Filter out internal fields
    summary_data = {
        k: v
        for k, v in session.items()
        if v is not None
        and k
        not in ["session_id", "current_question", "retry_count", "call_should_end"]
    }

    # Create a prompt for generating human-readable summary
    prompt = f"""You are a customer service representative having a natural conversation with a customer. 
Generate a simple, conversational summary in Hindi/Hinglish based on the following conversation data:

{summary_data}

Create a natural, human-like summary as if you're speaking directly to the customer:
1. Keep it short and simple - like you're talking on a phone call
2. Use natural Hindi/Hinglish - mix of Hindi and English as people speak
3. Focus on key payment details: amount, payment method, date
4. Write it as a single flowing sentence or two, not a formal list
5. Example format: "Aapne ₹3000 ka payment aapki EMI ke liye kiya tha aur ye aapne online madhyam se kiya hai."

Do NOT include:
- Formal greetings like "Namaste" or "Aapke survey ke anusaar"
- Bullet points or lists
- Long explanations
- "Summary" or "conversation" words

Just write the key information naturally as if speaking:
"""

    try:
        response = model.generate_content(prompt)
        if response and response.text:
            return response.text.strip()
        else:
            # Fallback to basic summary if LLM fails
            return generate_fallback_summary(summary_data)
    except Exception as e:
        print(f"Error generating summary: {e}")
        return generate_fallback_summary(summary_data)


def generate_fallback_summary(data: dict) -> str:
    """Generate a basic conversational summary if LLM fails"""
    summary_parts = []

    # Build natural conversational summary
    if data.get("amount") and data.get("mode_of_payment"):
        amount = data.get("amount")
        mode = data.get("mode_of_payment")
        # Convert mode to readable format
        mode_map = {
            "online": "online",
            "online_lan": "online",
            "online_field_executive": "online field executive",
            "cash": "cash",
            "branch": "branch",
            "outlet": "outlet",
            "nach": "NACH",
        }
        mode_text = mode_map.get(mode, mode)
        summary_parts.append(
            f"Aapne ₹{amount} ka payment aapki EMI ke liye kiya tha aur ye aapne {mode_text} madhyam se kiya hai."
        )
    elif data.get("amount"):
        summary_parts.append(
            f"Aapne ₹{data.get('amount')} ka payment aapki EMI ke liye kiya tha."
        )
    elif data.get("last_month_emi_payment") == "YES":
        summary_parts.append("Aapne pichle mahine EMI payment kiya tha.")

    if data.get("pay_date"):
        summary_parts.append(f"Aapki payment ki date {data.get('pay_date')} thi.")

    if not summary_parts:
        # Fallback if no key data
        summary_parts.append(
            "Aapne L&T Finance se loan liya hai aur aapne payment kiya hai."
        )

    return " ".join(summary_parts)


def is_survey_completed(session: dict) -> bool:
    """Check if survey is completed without modifying the session"""
    next_idx = get_next_question_index(session)
    return next_idx >= len(QUESTIONS) or session.get("call_should_end", False)


def get_closing_statement(session: dict) -> str:
    """Generate closing statement based on session data"""
    if session.get("call_should_end"):
        # Check if it's a wrong number case (loan_taken is NO)
        if session.get("loan_taken") == "NO":
            return "Dhanyawad aapke samay ke liye.\n" "Aapka din shubh ho!"
        # Otherwise, it's alternate contact case
        else:
            return (
                "Dhanyawad aapke samay ke liye.\n"
                "Hum aapke dwara bataye gaye samay par customer se sampark karenge.\n"
                "Aapka din shubh ho!"
            )
    else:
        return (
            "Dhanyawad aapke samay ke liye.\n"
            "Aapki feedback hamare liye bahut mahatvapurna hai.\n"
            "Aapka din shubh ho!"
        )
