from app.questions.base import QuestionResult
from app.llm.gemini_client import call_gemini
from app.config.settings import COMPANY_NAME, COMPANY_NAME_FORMAL, get_message


def get_text():
    return get_message("greeting")


def _get_prompt_template():
    """Get the prompt template with dynamic company name"""
    greeting_text = get_message("greeting")
    return f"""
You are an intelligent conversational AI assistant for {COMPANY_NAME_FORMAL}. You are conducting a customer survey call.

The agent just asked the caller:
"{greeting_text}"

You now receive the caller's reply (in Hindi, Hinglish, or English).

Your task is to:
1. Understand the caller's intent completely
2. Classify the response
3. Decide what action to take next
4. Generate an appropriate response if needed

CLASSIFICATION CATEGORIES:

1. "YES" → caller clearly confirms they are the intended person or is happy to continue.
   Examples: "हाँ", "जी हाँ", "हाँ मैं हूँ", "yes", "yes I am", "हाँ बोलीए", "हाँ जी"
   Action: Proceed to next question. No response needed.

2. "NO" → caller clearly says they are NOT that person (someone else / wrong number).
   Examples: "नहीं", "गलत नंबर", "मैं नहीं हूँ", "no", "wrong number", "मैं वो नहीं हूँ"
   Action: Proceed to ask for availability/alternate contact. No response needed.

2a. "NOT_AVAILABLE" → caller says the person is not available (brother, wife, family member speaking).
   Examples: "वह उपलब्ध नहीं हैं", "भाई बोल रहे हैं", "मैं उनकी पत्नी हूँ", "not available", "brother speaking"
   Action: Ask when they will be available OR explain the purpose of call. Generate appropriate response.

2b. "SENSITIVE_SITUATION" → caller mentions sensitive situation (death, serious illness, etc.).
   Examples: "उनका निधन हो गया", "वह अब नहीं रहे", "passed away", "death"
   Action: CLOSING with empathetic message. Generate compassionate closing message.

2c. "NAME_CORRECTION" → caller provides different/corrected name.
   Examples: "मेरा नाम अलोक पंजा है", "नाम गलत है", "name is Alok Panja not Alok Kumar Ray"
   Action: Acknowledge name correction, update, and continue. Generate acknowledgment response.

3. "ROLE_CLARIFICATION" → caller asks questions about who you are, who you're calling, or wants clarification 
   about the call purpose. They are NOT refusing, just seeking information before answering.
   Examples: 
   - "आप कोन बात कर रहे हू?" (Who are you speaking to?)
   - "आप कौन हो?" (Who are you?)
   - "क्या मेरी बात आकाश जी से हो रही है?" (Am I speaking to Akash ji?)
   - "क्यों कॉल कर रहे हो?" (Why are you calling?)
   - "आप किससे बात कर रहे हैं?" (Who are you talking to?)
   - "मैं कौन हूँ?" (Who am I?)
   - "कौन बोल रहा है?" (Who is speaking?)
   Action: Provide a friendly, clear explanation of your role and purpose, then repeat the original question.
   Response should be in natural Hindi, explaining: you are an AI assistant from {COMPANY_NAME_FORMAL} calling to gather 
   feedback about their payment experience, and then ask the identity question again.

4. "REFUSE" → caller explicitly refuses to talk, says they don't want to participate, or 
   aggressively ends the conversation.
   Examples: "मुझे बात नहीं करनी", "कॉल मत करो", "बंद करो", "मुझे इसमें दिलचस्पी नहीं है", 
   "I don't want to talk", "stop calling", "मत बुलाओ"
   Action: End the call gracefully. Generate a polite closing message.

5. "UNCLEAR" → reply is too ambiguous or unrelated to decide.
   Action: Ask the question again politely.

Return ONLY this JSON (no extra text):
{
  "value": "YES" | "NO" | "NOT_AVAILABLE" | "SENSITIVE_SITUATION" | "NAME_CORRECTION" | "ROLE_CLARIFICATION" | "REFUSE" | "UNCLEAR",
  "is_clear": true | false,
  "action": "NEXT" | "CLARIFY" | "REPEAT" | "CLOSING",
  "response_text": "string or null",
  "corrected_name": "string or null"
}

ACTION MEANINGS:
- "NEXT": Move to next question (for YES, NO)
- "CLARIFY": Provide clarification response then repeat question (for ROLE_CLARIFICATION)
- "REPEAT": Repeat the same question (for UNCLEAR)
- "CLOSING": End the call gracefully (for REFUSE)

RESPONSE_TEXT:
- For ROLE_CLARIFICATION: Generate a natural Hindi response explaining your role, then repeat the identity question
- For REFUSE: Generate a polite closing message in Hindi
- For UNCLEAR: Generate a polite request to repeat the answer
- For YES/NO: null (no response needed)

CRITICAL GUIDELINES:
- Analyze the caller's intent deeply. If they ask ANY question about identity, role, or call purpose, 
  it's ROLE_CLARIFICATION (cooperative), NOT REFUSE (uncooperative).
- If caller says person is NOT AVAILABLE (brother/wife speaking), classify as NOT_AVAILABLE.
  Generate response asking when they'll be available OR explaining call purpose.
- If caller mentions DEATH or serious situation, classify as SENSITIVE_SITUATION. 
  Generate empathetic closing message expressing condolences.
- If caller provides DIFFERENT NAME, classify as NAME_CORRECTION. Extract corrected_name and acknowledge.
- ROLE_CLARIFICATION responses should be friendly, informative, and natural. Include the customer name 
  in your response when repeating the question.
- REFUSE responses should be polite and professional, thanking them for their time.
- If you can confidently classify, set is_clear = true.
- Use UNCLEAR only when the intent truly cannot be determined.
- All response_text should be in natural, conversational Hindi (Devanagari script).
"""


def handle(user_input, session):
    """Handle user input using LLM to decide classification, action, and response"""
    customer_name = session.get("customer_name", "ग्राहक")
    
    # Get prompt template and replace placeholders
    PROMPT = _get_prompt_template()
    prompt_with_name = PROMPT.replace("{{customer_name}}", customer_name)
    
    r = call_gemini(prompt_with_name + "\n\nCaller's reply: " + user_input)
    
    # Log the raw response for debugging
    print(f"DEBUG q1_identity LLM response: {r}")
    
    value = r.get("value")
    is_clear = r.get("is_clear", False)
    action = r.get("action", "NEXT")
    response_text = r.get("response_text")
    
    if not is_clear:
        print(f"DEBUG: LLM returned unclear response for: '{user_input}'")
        # Even if unclear, check if LLM provided an action and response
        if action == "REPEAT" and response_text:
            session["needs_clarification"] = True
            session["clarification_response"] = response_text
            return QuestionResult(True, value="UNCLEAR", extra={"action": "REPEAT", "response_text": response_text})
        return QuestionResult(False)
    
    print(f"DEBUG: LLM classified '{user_input}' as: {value}, action: {action}")

    # Validate that value is one of the expected classifications
    valid_values = ["YES", "NO", "NOT_AVAILABLE", "SENSITIVE_SITUATION", "NAME_CORRECTION", "ROLE_CLARIFICATION", "REFUSE", "UNCLEAR"]
    if value not in valid_values:
        print(f"Warning: Unexpected value '{value}' from LLM, treating as UNCLEAR")
        return QuestionResult(False)

    # Store the raw classification
    session["identify_confirmation"] = value

    # Store LLM's decision about action and response
    session["llm_action"] = action
    session["llm_response_text"] = response_text

    # Handle based on LLM's decision
    if value == "SENSITIVE_SITUATION":
        print(f"DEBUG: Detected SENSITIVE_SITUATION for: '{user_input}'")
        session["call_should_end"] = True
        if response_text:
            session["closing_message"] = response_text
        else:
            session["closing_message"] = get_message("sensitive_situation")
        return QuestionResult(True, value="REFUSE", extra={"action": "CLOSING", "response_text": session["closing_message"]})
    
    if value == "NOT_AVAILABLE":
        print(f"DEBUG: Detected NOT_AVAILABLE for: '{user_input}'")
        session["needs_clarification"] = True
        if response_text:
            session["clarification_response"] = response_text
        else:
            not_available_msg = get_message("not_available").replace("{{customer_name}}", customer_name)
            session["clarification_response"] = not_available_msg
        return QuestionResult(True, value="NOT_AVAILABLE", extra={"action": "CLARIFY", "response_text": session["clarification_response"]})
    
    if value == "NAME_CORRECTION":
        print(f"DEBUG: Detected NAME_CORRECTION for: '{user_input}'")
        corrected_name = r.get("corrected_name")
        if corrected_name:
            session["customer_name"] = corrected_name
            session["name_corrected"] = True
        session["needs_clarification"] = True
        if response_text:
            session["clarification_response"] = response_text
        else:
            if corrected_name:
                session["clarification_response"] = get_message("name_corrected_with_name", corrected_name=corrected_name).replace("{{customer_name}}", corrected_name)
            else:
                session["clarification_response"] = get_message("name_corrected_generic").replace("{{customer_name}}", customer_name)
        return QuestionResult(True, value="NAME_CORRECTION", extra={"action": "CLARIFY", "response_text": session["clarification_response"]})
    
    if value == "ROLE_CLARIFICATION":
        print(f"DEBUG: Detected ROLE_CLARIFICATION for: '{user_input}'")
        session["needs_role_clarification"] = True
        # Use LLM-generated response if available, otherwise fallback
        if response_text:
            session["role_clarification_response"] = response_text
        else:
            # Fallback response if LLM didn't generate one
            role_clar_msg = get_message("role_clarification").replace("{{customer_name}}", customer_name)
            session["role_clarification_response"] = role_clar_msg
        return QuestionResult(True, value="ROLE_CLARIFICATION", extra={"action": action, "response_text": response_text})

    if value == "REFUSE":
        print(f"DEBUG: Detected REFUSE for: '{user_input}'")
        session["call_should_end"] = True
        # Store LLM-generated closing message if available
        if response_text:
            session["closing_message"] = response_text
        return QuestionResult(True, value="REFUSE", extra={"action": action, "response_text": response_text})

    if value == "UNCLEAR":
        print(f"DEBUG: Detected UNCLEAR for: '{user_input}'")
        if response_text:
            session["needs_clarification"] = True
            session["clarification_response"] = response_text
        return QuestionResult(True, value="UNCLEAR", extra={"action": action, "response_text": response_text})

    # For YES or NO, proceed normally
    print(f"DEBUG: Proceeding with value: {value}, action: {action}")
    return QuestionResult(True, value=value, extra={"action": action})
