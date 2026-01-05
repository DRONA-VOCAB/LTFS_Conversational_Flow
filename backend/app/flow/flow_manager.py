from flow.question_order import QUESTIONS
from config.settings import MAX_RETRIES
import importlib

def should_skip_question(q_name, session):
    """Check if a question should be skipped based on conditions"""
    # q2_availability: only ask if identity confirmation is NO
    if q_name == "q2_availability":
        return session.get("identify_confirmation") != "NO"
    
    # q6_payee_details: only ask if payee is not "self"
    if q_name == "q6_payee_details":
        return session.get("payee") == "self"
    
    # q9_executive_details: only ask if payment mode is online_field_executive or cash
    if q_name == "q9_executive_details":
        mode = session.get("mode_of_payment")
        return mode not in ["online_field_executive", "cash"]
    
    return False

def get_next_question_index(session):
    """Get the next question index, skipping optional questions that don't meet conditions"""
    current_idx = session["current_question"]
    
    # Find the next question that should be asked
    for idx in range(current_idx, len(QUESTIONS)):
        q_name = QUESTIONS[idx]
        if not should_skip_question(q_name, session):
            return idx
    
    # No more questions
    return len(QUESTIONS)

def get_question_text(session):
    """Get the text for the current question"""
    # Skip optional questions that don't meet conditions
    next_idx = get_next_question_index(session)
    if next_idx >= len(QUESTIONS):
        return None
    
    # Update current_question to the next valid question
    session["current_question"] = next_idx
    q_name = QUESTIONS[next_idx]
    
    # Import the question module
    module = importlib.import_module(f"questions.{q_name}")
    text = module.get_text()
    return text.replace("{{customer_name}}", session["customer_name"])

def process_answer(session, user_input):
    """Process the user's answer to the current question"""
    current_idx = session["current_question"]
    q_name = QUESTIONS[current_idx]
    
    # Import the question module
    module = importlib.import_module(f"questions.{q_name}")
    result = module.handle(user_input, session)

    if not result.is_clear:
        session["retry_count"] += 1
        if session["retry_count"] > MAX_RETRIES:
            return "END"
        return "REPEAT"

    session["retry_count"] = 0
    
    # If alternate number was captured in q2_availability, end the call
    if session.get("call_should_end"):
        return "COMPLETED"
    
    session["current_question"] += 1

    # Find next question (skipping optional ones)
    next_idx = get_next_question_index(session)
    
    if next_idx >= len(QUESTIONS):
        return "COMPLETED"
    
    session["current_question"] = next_idx
    return "NEXT"
