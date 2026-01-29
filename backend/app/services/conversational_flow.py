"""
Conversational Flow Service - Single Prompt Approach
Handles intelligent conversation flow with dynamic question skipping
"""

import logging
from typing import Dict, Any, Optional, List
from config.prompt import PROMPT as CONVERSATIONAL_PROMPT
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)

# Conditional import to avoid initialization issues during testing
try:
    from llm.gemini_client import call_gemini, call_gemini_with_tools
    LLM_AVAILABLE = True
except Exception as e:
    logger.warning(f"LLM not available: {e}")
    LLM_AVAILABLE = False

    def call_gemini(prompt):
        """Mock function when LLM is not available"""
        return {
            "bot_response": "कृपया दोबारा बताइए।",
            "extracted_data": {},
            "next_action": "continue",
            "call_end_reason": None,
        }

    def call_gemini_with_tools(prompt, session, user_input, conversation_stage):
        return call_gemini(prompt)


def process_conversational_response(
    user_input: str, session: Dict[str, Any], customer_name: str
) -> Dict[str, Any]:
    """
    Process user input using conversational AI approach with enhanced response handling
    """
    # Build context from current session
    logger.info("===== New Conversational Turn =====")
    logger.info("Customer Name: %s", customer_name)
    logger.info("User Input: %s", user_input)
    logger.info("Session (before): %s", session)
    current_data = {
        "identity_confirmed": session.get("identity_confirmed"),
        "loan_taken": session.get("loan_taken"),
        "last_month_payment": session.get("last_month_payment"),
        "payee": session.get("payee"),
        "payment_date": session.get("payment_date"),
        "payment_mode": session.get("payment_mode"),
        "payment_reason": session.get("payment_reason"),
        "payment_amount": session.get("payment_amount"),
    }

    # Determine conversation stage and what we're currently asking about
    conversation_stage = get_conversation_stage(session)
    missing_info = get_missing_information(session)
    logger.info("Conversation Stage: %s", conversation_stage)
    logger.info("Missing Information: %s", missing_info)

    # Check if all required info is collected to determine if summary should be provided
    all_info_collected = (
        current_data.get("identity_confirmed") == "YES"
        and current_data.get("loan_taken") == "YES"
        and current_data.get("last_month_payment") == "YES"
        and current_data.get("payee")
        and current_data.get("payment_date")
        and current_data.get("payment_mode")
        and current_data.get("payment_reason")
        and current_data.get("payment_amount")
    )

    # Check if this is a correction/editing request
    is_correction = any(
        keyword in user_input.lower()
        for keyword in [
            "गलत",
            "सही नहीं",
            "बदल",
            "संशोधन",
            "ठीक नहीं",
            "wrong",
            "incorrect",
            "change",
            "edit",
            "correction",
            "नहीं",
            "no" if session.get("generated_summary") else "",
        ]
    )

    # Build the full prompt; context comes only from tools (get_transcript_examples, get_session_summary)
    full_prompt = build_context_for_turn(
        user_input=user_input,
        session=session,
        customer_name=customer_name,
        conversation_stage=conversation_stage,
        current_data=current_data,
        missing_info=missing_info,
        all_info_collected=all_info_collected,
        is_correction=is_correction,
    )

    try:
        # Call LLM with context-catching tools
        response = call_gemini_with_tools(
            full_prompt, session, user_input, conversation_stage
        )
        logger.info("LLM Raw Response: %s", response)

        if response and isinstance(response, dict):
            # Update session with extracted data
            extracted_data = response.get("extracted_data", {})
            logger.info("Extracted Data from LLM: %s", response.get("extracted_data"))
            logger.info("Next Action from LLM: %s", response.get("next_action"))
            logger.info("Call End Reason from LLM: %s", response.get("call_end_reason"))

            for key, value in extracted_data.items():
                if value is not None and value != "null":
                    session[key] = value

            logger.info("Session (after): %s", session)

            # Store conversation notes for debugging/improvement
            session["last_conversation_notes"] = response.get("conversation_notes", "")

            # Check if summary was provided
            provide_summary = response.get("provide_summary", False)
            if provide_summary:
                # Store the summary for future reference
                session["generated_summary"] = response.get("bot_response", "")
                logger.info("📝 Summary provided in bot_response")

            return {
                "bot_response": response.get("bot_response", "कृपया दोबारा बताइए।"),
                "next_action": response.get("next_action", "continue"),
                "call_end_reason": response.get("call_end_reason"),
                "extracted_data": extracted_data,
                "conversation_notes": response.get("conversation_notes", ""),
                "provide_summary": provide_summary,
            }
        else:
            # Enhanced fallback response based on conversation stage
            logger.warning("Invalid LLM response, triggering enhanced fallback")

            return get_enhanced_fallback_response(
                user_input, session, conversation_stage
            )

    except Exception as e:
        logger.error(f"Error in conversational processing: {e}")
        return get_enhanced_fallback_response(user_input, session, conversation_stage)


def get_missing_information(session: Dict[str, Any]) -> list:
    """
    Get list of information still needed
    """
    missing = []

    if not session.get("identity_confirmed"):
        missing.append("identity confirmation")
    elif session.get("identity_confirmed") == "NO":
        return ["availability and alternate contact"]

    if not session.get("loan_taken"):
        missing.append("loan confirmation")
    elif session.get("loan_taken") == "NO":
        return ["call can end - no loan"]

    if not session.get("last_month_payment"):
        missing.append("last month payment confirmation")
    elif session.get("last_month_payment") == "NO":
        return ["call can end - no payment"]

    # Payment details
    if not session.get("payee"):
        missing.append("who made payment")
    if not session.get("payment_date"):
        missing.append("payment date")
    if not session.get("payment_mode"):
        missing.append("payment method")
    if not session.get("payment_reason"):
        missing.append("payment reason")
    if not session.get("payment_amount"):
        missing.append("payment amount")

    return missing


def get_enhanced_fallback_response(
    user_input: str, session: Dict[str, Any], stage: str
) -> Dict[str, Any]:
    """
    Provide completely dynamic fallback responses when LLM fails - no hardcoded responses
    """
    # Create dynamic fallback prompt
    logger.warning("Entering enhanced fallback response")
    logger.info("Fallback User Input: %s", user_input)
    logger.info("Fallback Stage: %s", stage)
    logger.info("Fallback Session: %s", session)

    fallback_prompt = f"""
You are a FEMALE customer service representative from L and T Finance. The main LLM system failed, so you need to provide a fallback response.

Current situation:
- Customer said: "{user_input}"
- Conversation stage: {stage}
- Session data: {session}

Generate a natural, contextual response as a female representative:
- Use feminine forms in Hindi
- Acknowledge what the customer said
- Respond appropriately to their input
- Keep the conversation moving forward
- Be empathetic and professional

Respond with JSON format:
{{
    "bot_response": "Your dynamic Hindi response as female representative",
    "next_action": "continue/summary/end_call",
    "call_end_reason": "null or reason",
    "extracted_data": {{}},
    "conversation_notes": "Fallback response generated"
}}
"""

    try:
        if LLM_AVAILABLE:
            response = call_gemini(fallback_prompt)
            if isinstance(response, dict):
                return response

        # Ultimate fallback - minimal dynamic response
        acknowledgments = ["जी, मैं समझ गई।", "ठीक है।", "जी हाँ।"]
        import random

        ack = random.choice(acknowledgments)

        return {
            "bot_response": f"{ack} कृपया दोबारा बताइए।",
            "next_action": "continue",
            "call_end_reason": None,
            "extracted_data": {},
            "conversation_notes": f"Ultimate fallback for stage: {stage}",
        }

    except Exception as e:
        logger.error(f"Error in dynamic fallback: {e}")
        return {
            "bot_response": "कृपया दोबारा बताइए।",
            "next_action": "continue",
            "call_end_reason": None,
            "extracted_data": {},
            "conversation_notes": "Error fallback",
        }


def analyze_response_type(user_input: str) -> str:
    """
    Analyze the type of user response to help with appropriate handling
    """
    user_input_lower = user_input.lower().strip()

    # Check for common patterns
    if not user_input_lower or len(user_input_lower) < 2:
        return "silence_or_minimal"

    # Long responses (might contain multiple information) - check first
    if len(user_input.split()) > 10:
        return "detailed_response"

    # Rude/angry responses
    rude_indicators = [
        "बकवास",
        "गलत",
        "परेशान",
        "व्यस्त",
        "समय नहीं",
        "बंद करो",
        "नहीं चाहिए",
    ]
    if any(indicator in user_input_lower for indicator in rude_indicators):
        return "frustrated_or_busy"

    # Confused responses
    confused_indicators = ["क्या", "कौन", "समझ नहीं", "पता नहीं", "मालूम नहीं"]
    if any(indicator in user_input_lower for indicator in confused_indicators):
        return "confused_or_unclear"

    # Positive/cooperative responses
    positive_indicators = ["हाँ", "जी", "ठीक", "सही", "बिल्कुल"]
    if any(indicator in user_input_lower for indicator in positive_indicators):
        return "cooperative"

    # Negative responses
    negative_indicators = ["नहीं", "ना", "नही"]
    if any(indicator in user_input_lower for indicator in negative_indicators):
        return "negative"

    # Minimal responses
    if len(user_input.strip()) <= 5:
        return "silence_or_minimal"

    return "neutral"


def get_conversation_stage(session: Dict[str, Any]) -> str:
    """
    Determine what stage of conversation we're in with enhanced logic
    """
    if not session.get("identity_confirmed"):
        return "identity_confirmation"
    elif session.get("identity_confirmed") == "NO":
        return "wrong_person_handling"
    elif not session.get("loan_taken"):
        return "loan_confirmation"
    elif session.get("loan_taken") == "NO":
        return "no_loan_handling"
    elif not session.get("last_month_payment"):
        return "payment_confirmation"
    elif session.get("last_month_payment") == "NO":
        return "no_payment_handling"
    elif not session.get("payee"):
        return "payee_identification"
    elif not session.get("payment_date"):
        return "date_collection"
    elif not session.get("payment_mode"):
        return "mode_collection"
    elif not session.get("payment_reason"):
        return "reason_collection"
    elif not session.get("payment_amount"):
        return "amount_collection"
    else:
        return "information_complete"


def get_fallback_response(
    user_input: str, session: Dict[str, Any], stage: str
) -> Dict[str, Any]:
    """
    Provide fallback responses when LLM fails - now calls enhanced version
    """
    return get_enhanced_fallback_response(user_input, session, stage)


def get_initial_greeting(customer_name: str) -> str:
    """
    Get the initial greeting message - completely dynamic, generated by LLM
    """
    # Create a dynamic prompt for initial greeting
    greeting_prompt = f"""
You are a FEMALE customer service representative from L and T Finance starting a feedback call.

Generate a natural, warm initial greeting in Hindi for customer: {customer_name}

Requirements:
- Use feminine form: "बात कर रही हूँ" (not "बात कर रहा हूँ")
- Be professional but warm
- Confirm you're speaking to the right person
- Sound natural and conversational
- Use the customer's name appropriately

Generate ONLY the greeting text in Hindi, nothing else.
"""

    try:
        if LLM_AVAILABLE:
            response = call_gemini(greeting_prompt)
            if isinstance(response, dict) and "bot_response" in response:
                return response["bot_response"]
            elif isinstance(response, str):
                return response.strip()

        # Fallback if LLM not available
        return f"नमस्ते, मैं एल एंड टी फाइनेंस की तरफ़ से बात कर रही हूँ, क्या मेरी बात {customer_name} जी से हो रही है?"

    except Exception as e:
        logger.error(f"Error generating dynamic greeting: {e}")
        # Fallback greeting
        return f"नमस्ते, मैं एल एंड टी फाइनेंस की तरफ़ से बात कर रही हूँ, क्या मेरी बात {customer_name} जी से हो रही है?"


def is_conversation_complete(session: Dict[str, Any]) -> bool:
    """
    Check if all required information has been collected
    """
    required_fields = [
        "identity_confirmed",
        "loan_taken",
        "last_month_payment",
        "payee",
        "payment_date",
        "payment_mode",
        "payment_reason",
        "payment_amount",
    ]

    # If identity not confirmed or no loan, conversation can end early
    if session.get("identity_confirmed") == "NO" or session.get("loan_taken") == "NO":
        return True

    # If no payment last month, we can end after confirming that
    if session.get("last_month_payment") == "NO":
        return True

    # Otherwise check if all payment-related fields are filled
    payment_fields = [
        "payee",
        "payment_date",
        "payment_mode",
        "payment_reason",
        "payment_amount",
    ]
    return all(session.get(field) for field in payment_fields)


def build_context_for_turn(
    user_input: str,
    session: Dict[str, Any],
    customer_name: str,
    conversation_stage: str,
    current_data: Dict[str, Any],
    missing_info: list,
    all_info_collected: bool,
    is_correction: bool,
) -> str:
    """
    Assemble the full prompt for Gemini using:
    - Core system prompt (`CONVERSATIONAL_PROMPT`)
    - Instruction to use get_transcript_examples / get_session_summary tools for context
    - Compact session state and current user input
    """
    examples_block = (
        "CONTEXT TOOLS: Use get_transcript_examples(phase, query, max_results) and/or get_session_summary() "
        "to fetch relevant call examples and session state before responding. Do not assume examples are in the prompt."
    )

    full_prompt = f"""
    {CONVERSATIONAL_PROMPT}

    {examples_block}

    CURRENT CONVERSATION CONTEXT:
    - Customer Name: {customer_name}
    - Conversation Stage: {conversation_stage}
    - Current Data Collected: {current_data}
    - Missing Information: {missing_info}
    - All Information Collected: {all_info_collected}
    - Is Correction Request: {is_correction}
    - Last Bot Response: {session.get('last_bot_response', 'Initial greeting')}
    - Previous Summary (if any): {session.get('generated_summary', 'None')}

    CUSTOMER'S RESPONSE: "{user_input}"

    ANALYSIS REQUIRED:
    1. What type of response is this? (clear answer, unclear, irrelevant, rude, confused, partial, correction, etc.)
    2. What information can be extracted from this response?
    3. Is this a correction/editing request? If yes, which field needs to be updated?
    4. How should I acknowledge their response?
    5. If all information is collected AND not a correction, provide summary in bot_response with provide_summary=true
    6. If this is a correction, update the field and provide updated summary
    7. What should I ask next or how should I redirect?

    REMEMBER:
    - ALWAYS acknowledge what they said first
    - Be patient and understanding regardless of their response type
    - Extract ANY useful information mentioned
    - Handle difficult customers with empathy
    - Keep the conversation natural and human-like
    - Don't repeat questions unnecessarily if information is already provided
    - When all info is collected, provide summary naturally in bot_response (set provide_summary=true)
    - If customer corrects information, update extracted_data and provide updated summary
    - After providing summary, wait for confirmation before ending call

    Based on the customer's response and current context, provide your response:
    """
    return full_prompt


def generate_conversation_summary(session: Dict[str, Any]) -> str:
    """
    Generate a completely dynamic summary of the collected information using LLM
    """
    logger.info("Generating conversation summary")
    logger.info("SSession Data for Summary: %s", session)

    summary_prompt = f"""
You are a FEMALE customer service representative from L and T Finance. Generate a natural, conversational summary of the customer feedback collected. Generate strciytly in devnagri script.

Session data collected:
{session}

Generate a natural summary in Hindi that:
- Uses feminine forms when referring to yourself
- Sounds conversational and human
- Includes the key payment information collected
- Asks for confirmation at the end
- Is brief but complete
- Sounds like you're speaking to the customer directly

Generate ONLY the summary text in Hindi, nothing else.
"""

    try:
        if LLM_AVAILABLE:
            response = call_gemini(summary_prompt)
            logger.info("Generated Summary: %s", response)

            if isinstance(response, dict) and "bot_response" in response:
                return response["bot_response"]
            elif isinstance(response, str):
                return response.strip()

        # Fallback summary generation
        logger.warning("Summary LLM failed, using fallback summary")

        return generate_fallback_summary_dynamic(session)

    except Exception as e:
        logger.error(f"Error generating dynamic summary: {e}")
        return generate_fallback_summary_dynamic(session)


def generate_fallback_summary_dynamic(session: Dict[str, Any]) -> str:
    """Generate a basic dynamic summary if LLM fails"""
    summary_parts = []

    # Build summary dynamically based on available data
    amount = session.get("payment_amount") or session.get("amount")
    mode = session.get("payment_mode") or session.get("mode_of_payment")
    date = session.get("payment_date") or session.get("pay_date")
    reason = session.get("payment_reason") or session.get("reason")

    if amount:
        summary_parts.append(f"₹{amount} का payment")

    if date:
        summary_parts.append(f"{date} तारीख को")

    if mode:
        mode_text = {
            "online_lan": "online",
            "online_field_executive": "field executive के द्वारा",
            "cash": "cash में",
            "branch": "branch में",
            "outlet": "outlet में",
            "nach": "NACH के द्वारा",
        }.get(mode, mode)
        summary_parts.append(f"{mode_text} किया गया")

    if reason:
        reason_text = {
            "emi": "EMI के लिए",
            "emi_charges": "EMI और charges के लिए",
            "settlement": "settlement के लिए",
        }.get(reason, f"{reason} के लिए")
        summary_parts.append(reason_text)

    if summary_parts:
        summary = "आपने " + " ".join(summary_parts) + " था। क्या यह जानकारी सही है?"
    else:
        summary = "आपकी payment की जानकारी record की गई है। क्या यह सही है?"

    return summary
