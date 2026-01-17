import logging
from .question_order import QUESTIONS
from ..config.settings import MAX_RETRIES
from ..services.summary_service import (
    generate_human_summary,
    get_closing_statement,
    detect_confirmation,
    detect_field_to_edit,
    get_edit_prompt,
)
from ..services.conversational_flow import (
    process_conversational_response,
    get_initial_greeting,
    is_conversation_complete,
    generate_conversation_summary
)
import importlib

logger = logging.getLogger(__name__)

# Flow phases
PHASE_QUESTIONS = "questions"
PHASE_CONVERSATION = "conversation"  # New conversational phase
PHASE_SUMMARY = "summary"  # Summary includes confirmation question
PHASE_EDIT = "edit"  # User wants to edit a field
PHASE_CLOSING = "closing"


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
    """Get the text for the current question - now uses conversational approach"""
    phase = session.get("phase", PHASE_CONVERSATION)
    
    # Use conversational approach instead of individual questions
    if phase == PHASE_CONVERSATION or not session.get("conversation_started"):
        # Start with initial greeting
        customer_name = session.get("customer_name", "")
        session["conversation_started"] = True
        session["phase"] = PHASE_CONVERSATION
        return get_initial_greeting(customer_name)
    
    # Fallback to old approach if needed (shouldn't happen in new system)
    if phase == PHASE_QUESTIONS:
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
    
    return None


def process_answer(session, user_input):
    """Process the user's answer - now uses conversational approach"""
    phase = session.get("phase", PHASE_CONVERSATION)

    # Handle summary phase (confirmation is embedded in summary)
    if phase == PHASE_SUMMARY:
        return handle_summary_response(session, user_input)

    # Handle edit phase
    if phase == PHASE_EDIT:
        return handle_edit_response(session, user_input)

    # Handle conversational phase (new approach)
    if phase == PHASE_CONVERSATION:
        return handle_conversational_response(session, user_input)

    # Handle old questions phase (fallback)
    if phase == PHASE_QUESTIONS:
        current_idx = session["current_question"]
        q_name = QUESTIONS[current_idx]
        logger.info(f"🔄 Processing answer for {q_name}: '{user_input}'")

        # Import the question module
        module = importlib.import_module(f"questions.{q_name}")
        result = module.handle(user_input, session)
        logger.info(
            f"📊 Result from {q_name}: is_clear={result.is_clear}, value={getattr(result, 'value', None)}"
        )

        if not result.is_clear:
            session["retry_count"] += 1
            if session["retry_count"] > MAX_RETRIES:
                return "END"
            return "REPEAT"

        session["retry_count"] = 0

        # If alternate number was captured or wrong number, go to closing
        if session.get("call_should_end"):
            session["phase"] = PHASE_CLOSING
            return "CLOSING"

        session["current_question"] += 1

        # Find next question (skipping optional ones)
        next_idx = get_next_question_index(session)

        if next_idx >= len(QUESTIONS):
            # All questions done, move to summary phase
            session["phase"] = PHASE_SUMMARY
            return "SUMMARY"

        session["current_question"] = next_idx
        return "NEXT"

    return "REPEAT"


def handle_conversational_response(session, user_input):
    """Handle user response in conversational mode"""
    logger.info(f"🔄 Processing conversational response: '{user_input}'")
    
    customer_name = session.get("customer_name", "")
    
    try:
        # Process the response using conversational AI
        result = process_conversational_response(user_input, session, customer_name)
        
        # Store the bot's response for TTS
        session["last_bot_response"] = result.get("bot_response", "")
        
        # Handle different next actions
        next_action = result.get("next_action", "continue")
        call_end_reason = result.get("call_end_reason")
        
        if next_action == "end_call":
            session["phase"] = PHASE_CLOSING
            session["call_should_end"] = True
            session["call_end_reason"] = call_end_reason
            return "CLOSING"
        elif next_action == "summary":
            session["phase"] = PHASE_SUMMARY
            return "SUMMARY"
        else:
            # Continue conversation
            return "CONTINUE_CONVERSATION"
            
    except Exception as e:
        logger.error(f"Error in conversational response: {e}")
        session["retry_count"] = session.get("retry_count", 0) + 1
        if session["retry_count"] > MAX_RETRIES:
            return "END"
        return "REPEAT"


def handle_summary_response(session, user_input):
    """Handle user response after hearing the summary (confirmation is embedded)"""
    logger.info(f"🔄 Processing summary confirmation: '{user_input}'")

    # Use LLM to detect confirmation
    confirmation = detect_confirmation(user_input)
    logger.info(f"📊 Confirmation result: {confirmation}")

    if confirmation == "YES":
        # User confirmed, move to closing
        session["phase"] = PHASE_CLOSING
        session["summary_confirmed"] = True
        return "CLOSING"
    elif confirmation == "NO":
        # User wants to edit, ask which field
        session["phase"] = PHASE_EDIT
        return "ASK_EDIT"
    else:
        # Unclear, repeat summary
        return "REPEAT_SUMMARY"


def handle_edit_response(session, user_input):
    """Handle user response when they want to edit a field"""
    logger.info(f"🔄 Processing edit request: '{user_input}'")

    # Use LLM to detect which field to edit
    edit_info = detect_field_to_edit(user_input, session)

    if edit_info:
        field = edit_info["field"]
        value = edit_info["value"]
        logger.info(f"📝 Editing field '{field}' to '{value}'")

        # Update the session field
        if field in session:
            session[field] = value
            session["phase"] = PHASE_CLOSING
            session["summary_confirmed"] = True
            return "CLOSING"

    # Could not detect, ask again
    logger.warning("⚠️ Could not detect field to edit")
    return "REPEAT_EDIT"


def get_summary_text(session):
    """Get the summary text for TTS (confirmation is included in summary)"""
    # Use conversational summary if available
    if session.get("phase") == PHASE_SUMMARY:
        summary = generate_conversation_summary(session)
        session["generated_summary"] = summary
        return summary
    
    # Fallback to old summary generation
    summary = generate_human_summary(session)
    session["generated_summary"] = summary
    return summary


def get_conversation_response_text(session):
    """Get the bot's response text for conversational mode"""
    return session.get("last_bot_response", "कृपया दोबारा बताइए।")


def get_edit_prompt_text():
    """Get the prompt asking which field to edit"""
    return get_edit_prompt()


def get_closing_text(session):
    """Get the closing statement for TTS"""
    return get_closing_statement(session)
