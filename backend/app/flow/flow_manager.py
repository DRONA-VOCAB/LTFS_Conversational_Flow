import logging
from flow.question_order import QUESTIONS
from config.settings import MAX_RETRIES
from services.summary_service import (
    generate_human_summary,
    get_closing_statement,
    detect_confirmation,
    detect_field_to_edit,
    get_edit_prompt,
)
import importlib

logger = logging.getLogger(__name__)

# Flow phases
PHASE_QUESTIONS = "questions"
PHASE_SUMMARY = "summary"  # Summary includes confirmation question
PHASE_EDIT = "edit"  # User wants to edit a field
PHASE_CLOSING = "closing"


def should_skip_question(q_name, session):
    """Check if a question should be skipped based on conditions"""
    # q2_availability: only ask if identity confirmation is NOT_AVAILABLE
    if q_name == "q2_availability":
        return session.get("identify_confirmation") != "NOT_AVAILABLE"

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
    # Check if we're in closing phase
    if session.get("phase") == PHASE_CLOSING:
        return None

    # Check if there's an acknowledgment text to speak first
    ack_text = session.pop("acknowledgment_text", None)
    if ack_text:
        # Return acknowledgment instead of question
        # The question will be asked in the next call
        return ack_text

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
    text = text.replace("{{customer_name}}", session.get("customer_name", ""))
    text = text.replace("{{product_type}}", session.get("product_type", "पर्सनल लोन"))
    return text


def process_answer(session, user_input):
    """Process the user's answer to the current question"""
    phase = session.get("phase", PHASE_QUESTIONS)

    # Handle summary phase (confirmation is embedded in summary)
    if phase == PHASE_SUMMARY:
        return handle_summary_response(session, user_input)

    # Handle edit phase
    if phase == PHASE_EDIT:
        return handle_edit_response(session, user_input)

    # Handle questions phase
    current_idx = session["current_question"]
    q_name = QUESTIONS[current_idx]
    logger.info("=" * 80)
    logger.info(
        f"📄 Processing answer for Question {current_idx + 1}/{len(QUESTIONS)}: {q_name}"
    )
    logger.info(f"User input: '{user_input}'")
    logger.info("-" * 80)

    # Import the question module
    module = importlib.import_module(f"questions.{q_name}")
    result = module.handle(user_input, session)

    logger.info(f"📊 QUESTIONS HANDLER RESULT FOR {q_name}:")
    logger.info(f"  - is_clear: {result.is_clear}")
    logger.info(f"  - value: {getattr(result, 'value', None)}")
    logger.info(f"  - extra: {getattr(result, 'extra', {})}")
    logger.info(f"  - response_text: {getattr(result, 'response_text', None)}")
    logger.info("=" * 80)

    # Check if action is CLOSING from LLM response
    action = None

    if hasattr(result, "extra") and result.extra:
        action = result.extra.get("action")

    print("ACTIONSSSS: ", action)

    if action == "CLOSING":
        session["phase"] = PHASE_CLOSING
        session["call_should_end"] = True

        # Store the closing message to be spoken
        response_text = result.extra.get("response_text")
        if response_text:
            session["closing_message"] = response_text
            logger.info(f"🛑 LLM returned action=CLOSING with message: {response_text}")
        else:
            logger.info("🛑 LLM returned action=CLOSING - ending call")

        return "CLOSING"

    if not result.is_clear:
        session["retry_count"] += 1
        if session["retry_count"] > MAX_RETRIES:
            session["phase"] = PHASE_CLOSING
            session["call_should_end"] = True
            return "END"

        # Store the acknowledgment/clarification response to be spoken
        response_text = getattr(result, "response_text", None)
        if response_text:
            # Store in session so get_question_text() will return it
            session["acknowledgment_text"] = response_text
            logger.info(f"💬 Stored acknowledgment text: {response_text}")

        # Don't increment current_question when is_clear=False
        return "REPEAT"

    session["retry_count"] = 0

    # Check if there's a response_text from the handler (for clarifications even when is_clear=True)
    response_text = None
    action = None
    if hasattr(result, "extra") and result.extra:
        response_text = result.extra.get("response_text")
        action = result.extra.get("action")

    elif hasattr(result, "response_text"):
        response_text = result.response_text

    # Special handling: If action is NEXT and there's response_text (e.g., YES_WITH_QUESTION),
    # concatenate the response with the next question and speak both together
    if action == "NEXT" and response_text:
        # Move to next question first
        session["current_question"] += 1

        # Find next question (skipping optional ones)
        next_idx = get_next_question_index(session)

        if next_idx >= len(QUESTIONS):
            # All questions done, move to summary phase
            session["phase"] = PHASE_SUMMARY
            response_text = response_text.replace(
                "{{customer_name}}", session.get("customer_name", "")
            )
            response_text = response_text.replace(
                "{{product_type}}", session.get("product_type", "पर्सनल लोन")
            )
            # Just speak the response, no next question
            session["acknowledgment_text"] = response_text
            logger.info(
                f"💬 Stored acknowledgment text (NEXT with response, no more questions): {response_text}"
            )
            return "SUMMARY"

        # Get the next question text
        session["current_question"] = next_idx
        q_name = QUESTIONS[next_idx]
        module = importlib.import_module(f"questions.{q_name}")
        next_question_text = module.get_text()

        response_text = response_text.replace(
            "{{customer_name}}", session.get("customer_name", "")
        )
        response_text = response_text.replace(
            "{{product_type}}", session.get("product_type", "टू-व्हीलर लोन")
        )

        next_question_text = next_question_text.replace(
            "{{customer_name}}", session.get("customer_name", "")
        )
        next_question_text = next_question_text.replace(
            "{{product_type}}", session.get("product_type", "टू-व्हीलर लोन")
        )

        # Concatenate response_text with next question
        combined_text = response_text + " " + next_question_text
        session["acknowledgment_text"] = combined_text
        logger.info(
            f"💬 Stored combined text (response + next question): {combined_text}"
        )

        # Move to the question after this one, so after speaking the combined text,
        # the next call to get_question_text will get the question after next_idx
        session["current_question"] = next_idx

        return "NEXT"

    # Regular handling: If there's response_text but action is not NEXT, repeat the question
    if response_text:
        session["acknowledgment_text"] = response_text
        logger.info(f"💬 Stored acknowledgment text (clear): {response_text}")
        # When we have a response_text (like ROLE_CLARIFICATION),
        # we should NOT move to next question yet. Return REPEAT to speak the
        # acknowledgment and then ask the SAME question again
        return "REPEAT"

    # If call should end flag is set, go to closing
    if session.get("call_should_end"):
        session["phase"] = PHASE_CLOSING
        return "CLOSING"

    # Now move to next question only if no response_text was set
    session["current_question"] += 1

    # Find next question (skipping optional ones)
    next_idx = get_next_question_index(session)

    if next_idx >= len(QUESTIONS):
        # All questions done, move to summary phase
        session["phase"] = PHASE_SUMMARY
        return "SUMMARY"

    session["current_question"] = next_idx
    return "NEXT"


def handle_summary_response(session, user_input):
    """Handle user response after hearing the summary (confirmation is embedded)"""
    logger.info("=" * 80)
    logger.info(f"📄 Processing summary confirmation")
    logger.info(f"User input: '{user_input}'")
    logger.info("-" * 80)

    # Use LLM to detect confirmation
    confirmation = detect_confirmation(user_input)
    logger.info(f"📊 Summary Confirmation Result: {confirmation}")

    if confirmation == "YES":
        # User confirmed, move to closing
        session["phase"] = PHASE_CLOSING
        session["summary_confirmed"] = True
        logger.info("✅ User confirmed summary - moving to closing phase")
        logger.info("=" * 80)
        return "CLOSING"
    elif confirmation == "NO":
        # User wants to edit, ask which field
        session["phase"] = PHASE_EDIT
        logger.info("❌ User wants to edit - moving to edit phase")
        logger.info("=" * 80)
        return "ASK_EDIT"
    else:
        # Unclear, repeat summary
        logger.warning("⚠️ Unclear confirmation - will repeat summary")
        logger.info("=" * 80)
        return "REPEAT_SUMMARY"


def handle_edit_response(session, user_input):
    """Handle user response when they want to edit a field"""
    logger.info("=" * 80)
    logger.info(f"📄 Processing edit request")
    logger.info(f"User input: '{user_input}'")
    logger.info("-" * 80)

    # Use LLM to detect which field to edit
    edit_info = detect_field_to_edit(user_input, session)

    if edit_info:
        field = edit_info["field"]
        new_value = edit_info["value"]
        old_value = session.get(field, None)

        logger.info(f"📝 Edit Detection Result:")
        logger.info(f"  - Field: {field}")
        logger.info(f"  - New Value: {new_value}")
        logger.info(f"  - Old Value: {old_value}")

        # Update the session field
        if field in session:
            # Store old value before updating
            old_value = session.get(field)

            # Update the field
            session[field] = new_value

            # Generate confirmation message in Hindi
            field_names_hindi = {
                "amount": "राशि",
                "pay_date": "भुगतान की तारीख",
                "mode_of_payment": "भुगतान का माध्यम",
                "payee": "किसने भुगतान किया",
                "reason": "भुगतान का कारण",
            }

            field_name_hindi = field_names_hindi.get(field, field)

            # Format old and new values for display
            old_value_display = str(old_value) if old_value else "कोई मान नहीं"
            new_value_display = str(new_value) if new_value else "कोई मान नहीं"

            # Generate confirmation message
            confirmation_message = f"जी, संपादन कर दिया गया है। {field_name_hindi} {old_value_display} से {new_value_display} में बदल दी गई है।"

            # Store confirmation message to be spoken before closing
            session["acknowledgment_text"] = confirmation_message
            session["phase"] = PHASE_CLOSING
            session["summary_confirmed"] = True

            logger.info(
                f"✅ Successfully updated field '{field}' - {old_value_display} → {new_value_display}"
            )
            logger.info(f"💬 Confirmation message: {confirmation_message}")
            logger.info("=" * 80)
            return "CLOSING"
        else:
            logger.warning(f"⚠️ Field '{field}' not found in session")
            logger.info("=" * 80)
            return "REPEAT_EDIT"

    # Could not detect, ask again
    logger.warning("⚠️ Could not detect field to edit - will ask again")
    logger.info("=" * 80)
    return "REPEAT_EDIT"


def get_summary_text(session):
    """Get the summary text for TTS (confirmation is included in summary)"""
    summary = generate_human_summary(session)
    session["generated_summary"] = summary
    return summary


def get_edit_prompt_text():
    """Get the prompt asking which field to edit"""
    return get_edit_prompt()


def get_closing_text(session):
    """Get the closing statement for TTS"""
    # Check if there's an acknowledgment text (e.g., edit confirmation) to speak first
    ack_text = session.pop("acknowledgment_text", None)
    if ack_text:
        # Store closing message separately so it's spoken after acknowledgment
        closing_message = session.get("closing_message")
        if closing_message:
            # Combine acknowledgment with closing message
            return ack_text + " " + closing_message
        return ack_text

    # Check if there's a custom closing message (e.g., from callback confirmation)
    if "closing_message" in session:
        return session["closing_message"]

    text = get_closing_statement(session)

    if text:
        return text
    else:
        return (
            "धन्यवाद आपके समय के लिए।\n"
            "आपकी फीडबैक हमारे लिए बहुत महत्वपूर्ण है।\n"
            "आपका दिन शुभ हो!"
        )
