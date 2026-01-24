#!/usr/bin/env python3
"""
Testing Matrix for LTFS Survey Call Flow
Tests complete conversation flows with realistic Hindi responses
Measures LLM latency for each turn

Usage:
    python3 backend/scripts/test_call_flow_matrix.py
"""

import sys
import time
import json
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# Add backend/app directory to path
backend_dir = Path(__file__).parent.parent
app_dir = backend_dir / "app"
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(app_dir))

from config.prompt import PROMPT as CONVERSATIONAL_PROMPT
from llm.gemini_client import call_gemini

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

#############################################################################
# CALL FLOW SCENARIOS
#############################################################################

CALL_FLOWS = [
    {
        "call_id": "CALL_001",
        "scenario": "Happy Path - Customer confirms identity, loan, and payment details",
        "customer_name": "राज कुमार",
        "product_type": "पर्सनल लोन",
        "conversation": [
            {
                "turn": 1,
                "bot_question": "नमस्ते राज कुमार जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात राज कुमार जी से हो रही है?",
                "user_response": "हाँ जी, मैं राज बोल रहा हूँ",
                "expected_extraction": {"identity_confirmed": "YES"}
            },
            {
                "turn": 2,
                "bot_question": None,  # LLM will generate dynamically
                "user_response": "हाँ, मैंने लोन लिया है",
                "expected_extraction": {"loan_taken": "YES"}
            },
            {
                "turn": 3,
                "bot_question": None,
                "user_response": "जी हाँ, पिछले महीने पेमेंट किया था",
                "expected_extraction": {"last_month_payment": "YES"}
            },
            {
                "turn": 4,
                "bot_question": None,
                "user_response": "मैंने खुद पेमेंट किया था",
                "expected_extraction": {"payee": "self"}
            },
            {
                "turn": 5,
                "bot_question": None,
                "user_response": "15 तारीख को पेमेंट किया था",
                "expected_extraction": {"payment_date": "15/01/2026"}
            },
            {
                "turn": 6,
                "bot_question": None,
                "user_response": "UPI से पेमेंट किया था",
                "expected_extraction": {"payment_mode": "online_lan"}
            },
            {
                "turn": 7,
                "bot_question": None,
                "user_response": "EMI के लिए पेमेंट किया था",
                "expected_extraction": {"payment_reason": "emi"}
            },
            {
                "turn": 8,
                "bot_question": None,
                "user_response": "5000 रुपये दिए थे",
                "expected_extraction": {"payment_amount": "5000"}
            }
        ]
    },
    {
        "call_id": "CALL_002",
        "scenario": "Relative answering - Brother provides details on behalf of customer",
        "customer_name": "आकाश शर्मा",
        "product_type": "होम लोन",
        "conversation": [
            {
                "turn": 1,
                "bot_question": "नमस्ते आकाश शर्मा जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात आकाश शर्मा जी से हो रही है?",
                "user_response": "नहीं, मैं उनका भाई बोल रहा हूँ",
                "expected_extraction": {"identity_confirmed": "NOT_AVAILABLE"}
            },
            {
                "turn": 2,
                "bot_question": None,
                "user_response": "मेरा नाम विक्रम है, मैं उनका छोटा भाई हूँ",
                "expected_extraction": {"speaker_name": "विक्रम", "speaker_relation": "भाई"}
            },
            {
                "turn": 3,
                "bot_question": None,
                "user_response": "हाँ, उन्होंने लोन लिया है",
                "expected_extraction": {"loan_taken": "YES"}
            },
            {
                "turn": 4,
                "bot_question": None,
                "user_response": "हाँ, पिछले महीने पेमेंट हुआ था",
                "expected_extraction": {"last_month_payment": "YES"}
            },
            {
                "turn": 5,
                "bot_question": None,
                "user_response": "मैंने खुद उनकी तरफ से पेमेंट किया था",
                "expected_extraction": {"payee": "relative"}
            },
            {
                "turn": 6,
                "bot_question": None,
                "user_response": "20 जनवरी को पेमेंट किया था",
                "expected_extraction": {"payment_date": "20/01/2026"}
            },
            {
                "turn": 7,
                "bot_question": None,
                "user_response": "ऑनलाइन NEFT से किया था",
                "expected_extraction": {"payment_mode": "online_lan"}
            },
            {
                "turn": 8,
                "bot_question": None,
                "user_response": "EMI और charges दोनों के लिए",
                "expected_extraction": {"payment_reason": "emi_charges"}
            },
            {
                "turn": 9,
                "bot_question": None,
                "user_response": "12000 रुपये थे",
                "expected_extraction": {"payment_amount": "12000"}
            }
        ]
    }
]

#############################################################################
# CONVERSATIONAL PROCESSING (Simplified version)
#############################################################################

def process_conversational_response(user_input: str, session: Dict, customer_name: str) -> Dict:
    """
    Simplified version of conversational flow processing for testing
    """
    # Build context from session
    current_data = {
        "identity_confirmed": session.get("identity_confirmed"),
        "loan_taken": session.get("loan_taken"),
        "last_month_payment": session.get("last_month_payment"),
        "payee": session.get("payee"),
        "payment_date": session.get("payment_date"),
        "payment_mode": session.get("payment_mode"),
        "payment_reason": session.get("payment_reason"),
        "payment_amount": session.get("payment_amount"),
        "speaker_name": session.get("speaker_name"),
        "speaker_relation": session.get("speaker_relation")
    }
    
    # Determine what's missing
    missing_info = []
    if current_data['identity_confirmed'] is None:
        missing_info.append("identity confirmation")
    if current_data['identity_confirmed'] == 'YES' and current_data['loan_taken'] is None:
        missing_info.append("loan confirmation")
    if current_data['loan_taken'] == 'YES' and current_data['last_month_payment'] is None:
        missing_info.append("last month payment")
    if current_data['last_month_payment'] == 'YES':
        if current_data['payee'] is None:
            missing_info.append("who made payment")
        if current_data['payment_date'] is None:
            missing_info.append("payment date")
        if current_data['payment_mode'] is None:
            missing_info.append("payment method")
        if current_data['payment_reason'] is None:
            missing_info.append("payment reason")
        if current_data['payment_amount'] is None:
            missing_info.append("payment amount")
    
    # Build prompt
    full_prompt = f"""
    {CONVERSATIONAL_PROMPT}

    CURRENT CONVERSATION CONTEXT:
    - Customer Name: {customer_name}
    - Current Data Collected: {current_data}
    - Missing Information: {missing_info}
    - Last Bot Response: {session.get('last_bot_response', 'Initial greeting')}

    CUSTOMER'S RESPONSE: "{user_input}"

    Based on the customer's response and current context, provide your response:
    """
    
    # Call LLM
    response = call_gemini(full_prompt)
    
    if response and isinstance(response, dict):
        return {
            "bot_response": response.get("bot_response", ""),
            "extracted_data": response.get("extracted_data", {}),
            "next_action": response.get("next_action", "continue"),
            "call_end_reason": response.get("call_end_reason")
        }
    
    return {
        "bot_response": "मुझे समझ नहीं आया, कृपया दोबारा बताइए।",
        "extracted_data": {},
        "next_action": "continue",
        "call_end_reason": None
    }

#############################################################################
# SESSION INITIALIZATION
#############################################################################

def initialize_session(customer_name: str, product_type: str) -> Dict:
    """Initialize a new session for testing"""
    return {
        "session_id": f"test_session_{int(time.time())}",
        "customer_name": customer_name,
        "customer_name_english": customer_name,
        "identity_confirmed": None,
        "loan_taken": None,
        "last_month_payment": None,
        "payee": None,
        "payment_date": None,
        "payment_mode": None,
        "payment_reason": None,
        "payment_amount": None,
        "conversation_started": True,
        "last_bot_response": None,
        "speaker_name": None,
        "speaker_relation": None,
        "current_question": 0,
        "retry_count": 0,
        "call_should_end": False,
        "call_end_reason": None,
        "phase": "conversation",
        "generated_summary": None,
        "summary_confirmed": False,
        "product_type": product_type
    }

#############################################################################
# TEST EXECUTION
#############################################################################

def run_call_flow_test(call_flow: Dict) -> Dict:
    """
    Run a single call flow test and collect metrics
    
    Returns:
        Dict with test results including latencies, responses, and success metrics
    """
    print(f"\n{'='*80}")
    print(f"{Colors.HEADER}{Colors.BOLD}🎯 {call_flow['call_id']}: {call_flow['scenario']}{Colors.ENDC}")
    print(f"{'='*80}")
    print(f"{Colors.OKCYAN}Customer: {call_flow['customer_name']}{Colors.ENDC}")
    print(f"{Colors.OKCYAN}Product: {call_flow['product_type']}{Colors.ENDC}")
    print(f"{'='*80}\n")
    
    # Initialize session
    session = initialize_session(call_flow['customer_name'], call_flow['product_type'])
    
    # Results collection
    test_results = {
        "call_id": call_flow['call_id'],
        "scenario": call_flow['scenario'],
        "customer_name": call_flow['customer_name'],
        "total_turns": len(call_flow['conversation']),
        "turns": [],
        "total_latency": 0,
        "avg_latency": 0,
        "success_rate": 0,
        "extractions_correct": 0,
        "extractions_total": 0
    }
    
    # Process each turn
    for conv_turn in call_flow['conversation']:
        turn_num = conv_turn['turn']
        bot_question = conv_turn.get('bot_question') or session.get('last_bot_response', '')
        user_response = conv_turn['user_response']
        expected_extraction = conv_turn.get('expected_extraction', {})
        
        print(f"{Colors.BOLD}Turn {turn_num}/{test_results['total_turns']}{Colors.ENDC}")
        print(f"{Colors.OKBLUE}🤖 BOT: {bot_question[:100]}...{Colors.ENDC}")
        print(f"{Colors.OKGREEN}👤 USER: {user_response}{Colors.ENDC}")
        
        # Measure latency
        start_time = time.time()
        
        try:
            # Process conversational response
            result = process_conversational_response(
                user_input=user_response,
                session=session,
                customer_name=call_flow['customer_name']
            )
            
            latency = time.time() - start_time
            
            # Extract bot response
            bot_response = result.get('bot_response', 'No response')
            extracted_data = result.get('extracted_data', {})
            
            print(f"{Colors.WARNING}⏱️  LATENCY: {latency:.2f}s{Colors.ENDC}")
            print(f"{Colors.OKCYAN}💬 BOT RESPONSE: {bot_response[:150]}...{Colors.ENDC}")
            print(f"📊 EXTRACTED: {json.dumps(extracted_data, ensure_ascii=False)}")
            
            # Update session with extracted data
            for key, value in extracted_data.items():
                if value is not None:
                    session[key] = value
            
            # Store last bot response
            session['last_bot_response'] = bot_response
            
            # Verify extractions
            extraction_correct = True
            for key, expected_value in expected_extraction.items():
                actual_value = extracted_data.get(key)
                if actual_value != expected_value:
                    extraction_correct = False
                    print(f"{Colors.FAIL}❌ Expected {key}={expected_value}, got {actual_value}{Colors.ENDC}")
                else:
                    print(f"{Colors.OKGREEN}✅ Correct: {key}={expected_value}{Colors.ENDC}")
            
            if extraction_correct:
                test_results['extractions_correct'] += 1
            test_results['extractions_total'] += 1
            
            # Store turn results
            turn_result = {
                "turn": turn_num,
                "bot_question": bot_question,
                "user_response": user_response,
                "bot_response": bot_response,
                "latency": latency,
                "extracted_data": extracted_data,
                "expected_extraction": expected_extraction,
                "extraction_correct": extraction_correct
            }
            test_results['turns'].append(turn_result)
            test_results['total_latency'] += latency
            
            print()
            
        except Exception as e:
            latency = time.time() - start_time
            print(f"{Colors.FAIL}❌ ERROR: {e}{Colors.ENDC}")
            turn_result = {
                "turn": turn_num,
                "error": str(e),
                "latency": latency
            }
            test_results['turns'].append(turn_result)
            print()
    
    # Calculate statistics
    test_results['avg_latency'] = test_results['total_latency'] / test_results['total_turns']
    test_results['success_rate'] = (test_results['extractions_correct'] / test_results['extractions_total'] * 100) if test_results['extractions_total'] > 0 else 0
    
    # Print summary
    print(f"\n{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}📊 CALL SUMMARY{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"Total Turns: {test_results['total_turns']}")
    print(f"Total Latency: {test_results['total_latency']:.2f}s")
    print(f"Average Latency: {test_results['avg_latency']:.2f}s/turn")
    print(f"Extraction Success: {test_results['extractions_correct']}/{test_results['extractions_total']} ({test_results['success_rate']:.1f}%)")
    print(f"{Colors.BOLD}{'='*80}{Colors.ENDC}\n")
    
    return test_results

#############################################################################
# MAIN
#############################################################################

def main():
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("=" * 80)
    print("🧪 LTFS SURVEY CALL FLOW TESTING MATRIX")
    print("=" * 80)
    print(f"{Colors.ENDC}")
    print(f"Testing {len(CALL_FLOWS)} call flow scenarios")
    print(f"Measuring LLM latency and extraction accuracy")
    print()
    
    all_results = []
    
    # Run each call flow test
    for call_flow in CALL_FLOWS:
        result = run_call_flow_test(call_flow)
        all_results.append(result)
        time.sleep(1)  # Small delay between calls
    
    # Overall statistics
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("=" * 80)
    print("📈 OVERALL TEST STATISTICS")
    print("=" * 80)
    print(f"{Colors.ENDC}")
    
    total_turns = sum(r['total_turns'] for r in all_results)
    total_latency = sum(r['total_latency'] for r in all_results)
    avg_latency = total_latency / total_turns if total_turns > 0 else 0
    total_correct = sum(r['extractions_correct'] for r in all_results)
    total_extractions = sum(r['extractions_total'] for r in all_results)
    overall_success = (total_correct / total_extractions * 100) if total_extractions > 0 else 0
    
    print(f"Total Calls: {len(all_results)}")
    print(f"Total Turns: {total_turns}")
    print(f"Total Time: {total_latency:.2f}s")
    print(f"Average Latency: {avg_latency:.2f}s/turn")
    print(f"Overall Success Rate: {total_correct}/{total_extractions} ({overall_success:.1f}%)")
    
    # Per-call breakdown
    print(f"\n{Colors.BOLD}Per-Call Breakdown:{Colors.ENDC}")
    for result in all_results:
        print(f"\n  {result['call_id']}: {result['scenario'][:50]}...")
        print(f"    Turns: {result['total_turns']}, Avg Latency: {result['avg_latency']:.2f}s, Success: {result['success_rate']:.1f}%")
    
    # Save results to file
    output_file = Path(__file__).parent / "test_results_call_flow_matrix.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n{Colors.OKGREEN}✅ Results saved to: {output_file}{Colors.ENDC}")
    print()

if __name__ == "__main__":
    main()

