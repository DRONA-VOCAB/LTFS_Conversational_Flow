def create_session(session_id, customer_name):
    return {
        "session_id": session_id,
        "customer_name": customer_name,  # Devanagari name for TTS
        "customer_name_english": None,   # Original English name (set in routes)
        "identify_confirmation": None,
        "availability": None,
        "user_contact": None,
        "loan_taken": None,
        "last_month_emi_payment": None,
        "payee": None,
        "payee_name": None,
        "payee_contact": None,
        "pay_date": None,
        "mode_of_payment": None,
        "field_executive_name": None,
        "field_executive_contact": None,
        "reason": None,
        "amount": None,
        "current_question": 0,
        "retry_count": 0,
        "call_should_end": False,
        "phase": "questions",  # Tracks flow: questions -> summary -> confirmation -> closing
        "generated_summary": None,
        "summary_confirmed": False,
    }
