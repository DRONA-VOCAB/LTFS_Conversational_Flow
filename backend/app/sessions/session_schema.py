def create_session(session_id, customer_name):
    return {
        "session_id": session_id,
        "customer_name": customer_name,  # Devanagari name for TTS
        "customer_name_english": None,   # Original English name (set in routes)
        
        # Conversational fields (new approach)
        "identity_confirmed": None,
        "loan_taken": None,
        "last_month_payment": None,
        "payee": None,  # self/family/friend/third_party
        "payment_date": None,
        "payment_mode": None,  # online_lan/online_field_executive/cash/branch/outlet/nach
        "payment_reason": None,  # emi/emi_charges/settlement/foreclosure/charges/loan_cancellation/advance_emi
        "payment_amount": None,
        "conversation_started": False,
        "last_bot_response": None,
        
        # Legacy fields (for backward compatibility)
        "identify_confirmation": None,
        "availability": None,
        "user_contact": None,
        "last_month_emi_payment": None,
        "payee_name": None,
        "payee_contact": None,
        "pay_date": None,
        "mode_of_payment": None,
        "field_executive_name": None,
        "field_executive_contact": None,
        "reason": None,
        "amount": None,
        
        # Flow control
        "current_question": 0,
        "retry_count": 0,
        "call_should_end": False,
        "call_end_reason": None,
        "phase": "conversation",  # conversation -> summary -> edit -> closing
        "generated_summary": None,
        "summary_confirmed": False,
    }
