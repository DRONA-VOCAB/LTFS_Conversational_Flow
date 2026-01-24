#!/usr/bin/env python3
"""
Comprehensive 15-Call Testing Matrix for LTFS Survey Flow
Outputs results to CSV for easy analysis

Usage:
    python3 backend/scripts/test_15_call_matrix.py
"""

import sys
import time
import json
import csv
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# Add backend directory to path
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

#############################################################################
# 15 COMPREHENSIVE CALL FLOW SCENARIOS
#############################################################################

CALL_FLOWS = [
    # 1. Happy Path - Complete details
    {
        "call_id": "CALL_001",
        "scenario": "Happy Path - Customer confirms all details smoothly",
        "customer_name": "राज कुमार",
        "product_type": "पर्सनल लोन",
        "conversation": [
            {"turn": 1, "bot_question": "नमस्ते राज कुमार जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात राज कुमार जी से हो रही है?", "user_response": "हाँ जी, मैं राज बोल रहा हूँ"},
            {"turn": 2, "user_response": "हाँ, मैंने लोन लिया है"},
            {"turn": 3, "user_response": "जी हाँ, पिछले महीने पेमेंट किया था"},
            {"turn": 4, "user_response": "मैंने खुद पेमेंट किया था"},
            {"turn": 5, "user_response": "15 तारीख को पेमेंट किया था"},
            {"turn": 6, "user_response": "UPI से पेमेंट किया था"},
            {"turn": 7, "user_response": "EMI के लिए पेमेंट किया था"},
            {"turn": 8, "user_response": "5000 रुपये दिए थे"},
        ]
    },
    
    # 2. Relative Answering - Brother helps
    {
        "call_id": "CALL_002",
        "scenario": "Relative (Brother) provides all details",
        "customer_name": "आकाश शर्मा",
        "product_type": "होम लोन",
        "conversation": [
            {"turn": 1, "bot_question": "नमस्ते आकाश शर्मा जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात आकाश शर्मा जी से हो रही है?", "user_response": "नहीं, मैं उनका भाई बोल रहा हूँ"},
            {"turn": 2, "user_response": "मेरा नाम विक्रम है"},
            {"turn": 3, "user_response": "हाँ, उन्होंने लोन लिया है"},
            {"turn": 4, "user_response": "जी हाँ, पिछले महीने पेमेंट हुआ था"},
            {"turn": 5, "user_response": "मैंने उनकी तरफ से पेमेंट किया था"},
            {"turn": 6, "user_response": "20 जनवरी को पेमेंट किया था"},
            {"turn": 7, "user_response": "ऑनलाइन NEFT से किया था"},
            {"turn": 8, "user_response": "EMI और charges दोनों के लिए"},
            {"turn": 9, "user_response": "12000 रुपये थे"},
        ]
    },
    
    # 3. Wrong Number
    {
        "call_id": "CALL_003",
        "scenario": "Wrong Number - Customer not found",
        "customer_name": "प्रिया वर्मा",
        "product_type": "कार लोन",
        "conversation": [
            {"turn": 1, "bot_question": "नमस्ते प्रिया वर्मा जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात प्रिया वर्मा जी से हो रही है?", "user_response": "गलत नंबर है, यहाँ कोई प्रिया नहीं है"},
        ]
    },
    
    # 4. No Loan Taken
    {
        "call_id": "CALL_004",
        "scenario": "Customer confirms identity but says no loan taken",
        "customer_name": "अमित पटेल",
        "product_type": "बिजनेस लोन",
        "conversation": [
            {"turn": 1, "bot_question": "नमस्ते अमित पटेल जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात अमित पटेल जी से हो रही है?", "user_response": "हाँ, मैं अमित बोल रहा हूँ"},
            {"turn": 2, "user_response": "नहीं, मैंने कोई लोन नहीं लिया है"},
        ]
    },
    
    # 5. Payment Not Made Last Month
    {
        "call_id": "CALL_005",
        "scenario": "Customer has loan but didn't pay last month",
        "customer_name": "सुनीता देसाई",
        "product_type": "पर्सनल लोन",
        "conversation": [
            {"turn": 1, "bot_question": "नमस्ते सुनीता देसाई जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात सुनीता देसाई जी से हो रही है?", "user_response": "हाँ जी, मैं सुनीता हूँ"},
            {"turn": 2, "user_response": "हाँ, मैंने लोन लिया है"},
            {"turn": 3, "user_response": "नहीं, पिछले महीने पेमेंट नहीं किया"},
        ]
    },
    
    # 6. Cash Payment to Field Executive
    {
        "call_id": "CALL_006",
        "scenario": "Cash payment given to field executive",
        "customer_name": "रमेश कुमार",
        "product_type": "होम लोन",
        "conversation": [
            {"turn": 1, "bot_question": "नमस्ते रमेश कुमार जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात रमेश कुमार जी से हो रही है?", "user_response": "हाँ जी"},
            {"turn": 2, "user_response": "हाँ, लोन लिया है"},
            {"turn": 3, "user_response": "हाँ, पिछले महीने दिया था"},
            {"turn": 4, "user_response": "मैंने खुद दिया था"},
            {"turn": 5, "user_response": "10 तारीख को दिया था"},
            {"turn": 6, "user_response": "फील्ड एग्जीक्यूटिव को कैश में दिया था"},
            {"turn": 7, "user_response": "उनका नाम संजय था, नंबर याद नहीं"},
            {"turn": 8, "user_response": "EMI के लिए दिया था"},
            {"turn": 9, "user_response": "8000 रुपये दिए थे"},
        ]
    },
    
    # 7. Branch Payment for Foreclosure
    {
        "call_id": "CALL_007",
        "scenario": "Customer paid at branch for foreclosure",
        "customer_name": "नीलम सिंह",
        "product_type": "कार लोन",
        "conversation": [
            {"turn": 1, "bot_question": "नमस्ते नीलम सिंह जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात नीलम सिंह जी से हो रही है?", "user_response": "हाँ जी, मैं नीलम हूँ"},
            {"turn": 2, "user_response": "हाँ, लोन लिया था"},
            {"turn": 3, "user_response": "हाँ, पिछले महीने पेमेंट किया था"},
            {"turn": 4, "user_response": "मैंने खुद किया था"},
            {"turn": 5, "user_response": "25 तारीख को किया था"},
            {"turn": 6, "user_response": "ब्रांच में जाकर दिया था"},
            {"turn": 7, "user_response": "फोरक्लोज़र के लिए पूरा पेमेंट किया था"},
            {"turn": 8, "user_response": "50000 रुपये दिए थे"},
        ]
    },
    
    # 8. NACH Auto-debit
    {
        "call_id": "CALL_008",
        "scenario": "NACH auto-debit payment",
        "customer_name": "अर्जुन मेहता",
        "product_type": "पर्सनल लोन",
        "conversation": [
            {"turn": 1, "bot_question": "नमस्ते अर्जुन मेहता जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात अर्जुन मेहता जी से हो रही है?", "user_response": "हाँ"},
            {"turn": 2, "user_response": "हाँ, लोन है"},
            {"turn": 3, "user_response": "हाँ, पिछले महीने हो गया"},
            {"turn": 4, "user_response": "ऑटो डेबिट से कट गया था बैंक से"},
            {"turn": 5, "user_response": "NACH के through automatic कट गया"},
            {"turn": 6, "user_response": "EMI के लिए"},
            {"turn": 7, "user_response": "6500 रुपये कटे थे"},
        ]
    },
    
    # 9. UPI with Clarifications
    {
        "call_id": "CALL_009",
        "scenario": "UPI payment with some confusion and clarifications",
        "customer_name": "पूजा शर्मा",
        "product_type": "होम लोन",
        "conversation": [
            {"turn": 1, "bot_question": "नमस्ते पूजा शर्मा जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात पूजा शर्मा जी से हो रही है?", "user_response": "हाँ जी"},
            {"turn": 2, "user_response": "हाँ, लोन लिया है"},
            {"turn": 3, "user_response": "हाँ... मतलब... हाँ किया था"},
            {"turn": 4, "user_response": "मैंने खुद"},
            {"turn": 5, "user_response": "कौन सी तारीख? अरे हाँ, 18 तारीख को था"},
            {"turn": 6, "user_response": "फोन से UPI किया था"},
            {"turn": 7, "user_response": "EMI और कुछ charges भी थे"},
            {"turn": 8, "user_response": "15500 रुपये थे शायद"},
        ]
    },
    
    # 10. Settlement with Corrections
    {
        "call_id": "CALL_010",
        "scenario": "Customer corrects information mid-conversation",
        "customer_name": "विकास रेड्डी",
        "product_type": "बिजनेस लोन",
        "conversation": [
            {"turn": 1, "bot_question": "नमस्ते विकास रेड्डी जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात विकास रेड्डी जी से हो रही है?", "user_response": "हाँ जी, मैं विकास हूँ"},
            {"turn": 2, "user_response": "हाँ, लोन लिया है"},
            {"turn": 3, "user_response": "हाँ, payment किया है"},
            {"turn": 4, "user_response": "मैंने खुद किया था"},
            {"turn": 5, "user_response": "12 तारीख को... नहीं नहीं, 14 तारीख को"},
            {"turn": 6, "user_response": "RTGS से किया था"},
            {"turn": 7, "user_response": "Settlement के लिए"},
            {"turn": 8, "user_response": "35000 rupees"},
        ]
    },
    
    # 11. Customer Asks Questions
    {
        "call_id": "CALL_011",
        "scenario": "Customer asks questions during call",
        "customer_name": "अनिता गुप्ता",
        "product_type": "पर्सनल लोन",
        "conversation": [
            {"turn": 1, "bot_question": "नमस्ते अनिता गुप्ता जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात अनिता गुप्ता जी से हो रही है?", "user_response": "हाँ, लेकिन यह कॉल किस बारे में है?"},
            {"turn": 2, "user_response": "अच्छा ठीक है, हाँ मैंने लोन लिया है"},
            {"turn": 3, "user_response": "हाँ, पेमेंट किया था"},
            {"turn": 4, "user_response": "मैंने खुद"},
            {"turn": 5, "user_response": "22 को"},
            {"turn": 6, "user_response": "Online UPI से"},
            {"turn": 7, "user_response": "EMI के लिए"},
            {"turn": 8, "user_response": "7000"},
        ]
    },
    
    # 12. Unclear/Noisy Responses
    {
        "call_id": "CALL_012",
        "scenario": "Some unclear responses simulating ASR errors",
        "customer_name": "मनोज कुमार",
        "product_type": "कार लोन",
        "conversation": [
            {"turn": 1, "bot_question": "नमस्ते मनोज कुमार जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात मनोज कुमार जी से हो रही है?", "user_response": "हाँ... मैं..."},
            {"turn": 2, "user_response": "लोन... हाँ"},
            {"turn": 3, "user_response": "पिछले... हाँ... किया"},
            {"turn": 4, "user_response": "मैं... खुद"},
            {"turn": 5, "user_response": "तारीख... 5... नहीं 6"},
            {"turn": 6, "user_response": "UPI"},
            {"turn": 7, "user_response": "EMI"},
            {"turn": 8, "user_response": "नौ हजार"},
        ]
    },
    
    # 13. Friend Made Payment
    {
        "call_id": "CALL_013",
        "scenario": "Customer's friend made the payment",
        "customer_name": "राहुल जोशी",
        "product_type": "पर्सनल लोन",
        "conversation": [
            {"turn": 1, "bot_question": "नमस्ते राहुल जोशी जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात राहुल जोशी जी से हो रही है?", "user_response": "हाँ जी"},
            {"turn": 2, "user_response": "हाँ, लोन है"},
            {"turn": 3, "user_response": "हाँ, payment हुआ"},
            {"turn": 4, "user_response": "मेरे दोस्त ने किया था"},
            {"turn": 5, "user_response": "उसका नाम करण है"},
            {"turn": 6, "user_response": "8 तारीख को"},
            {"turn": 7, "user_response": "उसने online किया था"},
            {"turn": 8, "user_response": "EMI के लिए"},
            {"turn": 9, "user_response": "4500 रुपये"},
        ]
    },
    
    # 14. Wife Provides Details
    {
        "call_id": "CALL_014",
        "scenario": "Wife answers and provides all details",
        "customer_name": "संजय त्रिपाठी",
        "product_type": "होम लोन",
        "conversation": [
            {"turn": 1, "bot_question": "नमस्ते संजय त्रिपाठी जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात संजय त्रिपाठी जी से हो रही है?", "user_response": "नहीं, मैं उनकी पत्नी हूँ"},
            {"turn": 2, "user_response": "मेरा नाम प्रिया है"},
            {"turn": 3, "user_response": "हाँ, उन्होंने होम लोन लिया है"},
            {"turn": 4, "user_response": "हाँ, पिछले महीने payment हुआ था"},
            {"turn": 5, "user_response": "मैंने ही किया था उनकी तरफ से"},
            {"turn": 6, "user_response": "12 जनवरी को"},
            {"turn": 7, "user_response": "ऑनलाइन NEFT से"},
            {"turn": 8, "user_response": "EMI के लिए"},
            {"turn": 9, "user_response": "18000 रुपये"},
        ]
    },
    
    # 15. Sensitive Situation
    {
        "call_id": "CALL_015",
        "scenario": "Sensitive situation - Customer passed away",
        "customer_name": "हरीश चौधरी",
        "product_type": "पर्सनल लोन",
        "conversation": [
            {"turn": 1, "bot_question": "नमस्ते हरीश चौधरी जी, मैं एल एंड टी फाइनेंस की तरफ से बात कर रही हूँ। क्या मेरी बात हरीश चौधरी जी से हो रही है?", "user_response": "वो अब नहीं रहे, उनका निधन हो गया"},
        ]
    },
]

#############################################################################
# CONVERSATIONAL PROCESSING
#############################################################################

def process_conversational_response(user_input: str, session: Dict, customer_name: str) -> Dict:
    """Simplified conversational flow processing"""
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
    
    response = call_gemini(full_prompt)
    
    if response and isinstance(response, dict):
        return {
            "bot_response": response.get("bot_response", ""),
            "extracted_data": response.get("extracted_data", {}),
            "next_action": response.get("next_action", "continue"),
            "call_end_reason": response.get("call_end_reason")
        }
    
    return {
        "bot_response": "मुझे समझ नहीं आया।",
        "extracted_data": {},
        "next_action": "continue",
        "call_end_reason": None
    }

#############################################################################
# SESSION & TEST EXECUTION
#############################################################################

def initialize_session(customer_name: str, product_type: str) -> Dict:
    """Initialize a new session"""
    return {
        "session_id": f"test_session_{int(time.time())}",
        "customer_name": customer_name,
        "identity_confirmed": None,
        "loan_taken": None,
        "last_month_payment": None,
        "payee": None,
        "payment_date": None,
        "payment_mode": None,
        "payment_reason": None,
        "payment_amount": None,
        "speaker_name": None,
        "speaker_relation": None,
        "conversation_started": True,
        "last_bot_response": None,
        "product_type": product_type
    }

def run_call_flow_test(call_flow: Dict) -> Dict:
    """Run a single call flow test"""
    print(f"\n{Colors.BOLD}{call_flow['call_id']}: {call_flow['scenario']}{Colors.ENDC}")
    
    session = initialize_session(call_flow['customer_name'], call_flow['product_type'])
    
    csv_rows = []
    total_latency = 0
    
    for conv_turn in call_flow['conversation']:
        turn_num = conv_turn['turn']
        bot_question = conv_turn.get('bot_question') or session.get('last_bot_response', '')
        user_response = conv_turn['user_response']
        
        print(f"  Turn {turn_num}: ", end='', flush=True)
        
        start_time = time.time()
        
        try:
            result = process_conversational_response(
                user_input=user_response,
                session=session,
                customer_name=call_flow['customer_name']
            )
            
            latency = time.time() - start_time
            total_latency += latency
            
            bot_response = result.get('bot_response', '')
            extracted_data = result.get('extracted_data', {})
            
            # Update session
            for key, value in extracted_data.items():
                if value is not None:
                    session[key] = value
            session['last_bot_response'] = bot_response
            
            # Create CSV row
            csv_row = {
                'call_id': call_flow['call_id'],
                'scenario': call_flow['scenario'],
                'customer_name': call_flow['customer_name'],
                'turn': turn_num,
                'user_response': user_response,
                'bot_response': bot_response,
                'latency_seconds': round(latency, 2),
                'identity_confirmed': extracted_data.get('identity_confirmed', ''),
                'speaker_name': extracted_data.get('speaker_name', ''),
                'speaker_relation': extracted_data.get('speaker_relation', ''),
                'loan_taken': extracted_data.get('loan_taken', ''),
                'last_month_payment': extracted_data.get('last_month_payment', ''),
                'payee': extracted_data.get('payee', ''),
                'payment_date': extracted_data.get('payment_date', ''),
                'payment_mode': extracted_data.get('payment_mode', ''),
                'payment_reason': extracted_data.get('payment_reason', ''),
                'payment_amount': extracted_data.get('payment_amount', ''),
            }
            csv_rows.append(csv_row)
            
            print(f"{latency:.2f}s ✓")
            
        except Exception as e:
            print(f"ERROR: {e}")
            latency = time.time() - start_time
            csv_rows.append({
                'call_id': call_flow['call_id'],
                'scenario': call_flow['scenario'],
                'turn': turn_num,
                'user_response': user_response,
                'error': str(e),
                'latency_seconds': round(latency, 2)
            })
    
    avg_latency = total_latency / len(call_flow['conversation']) if call_flow['conversation'] else 0
    print(f"  Avg Latency: {avg_latency:.2f}s, Total: {total_latency:.2f}s")
    
    return {
        'call_id': call_flow['call_id'],
        'csv_rows': csv_rows,
        'total_latency': total_latency,
        'avg_latency': avg_latency
    }

#############################################################################
# MAIN
#############################################################################

def main():
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("=" * 80)
    print("🧪 LTFS 15-CALL COMPREHENSIVE TEST MATRIX")
    print("=" * 80)
    print(f"{Colors.ENDC}")
    print(f"Testing {len(CALL_FLOWS)} diverse call scenarios")
    print(f"Output: ltfs_mistral_15call.csv\n")
    
    all_csv_rows = []
    all_results = []
    
    start_time = time.time()
    
    for i, call_flow in enumerate(CALL_FLOWS, 1):
        print(f"\n[{i}/{len(CALL_FLOWS)}] ", end='')
        result = run_call_flow_test(call_flow)
        all_csv_rows.extend(result['csv_rows'])
        all_results.append(result)
        time.sleep(0.5)  # Small delay between calls
    
    total_time = time.time() - start_time
    
    # Write CSV
    csv_file = Path(__file__).parent.parent.parent / "ltfs_mistral_15call.csv"
    
    fieldnames = [
        'call_id', 'scenario', 'customer_name', 'turn', 'user_response', 
        'bot_response', 'latency_seconds',
        'identity_confirmed', 'speaker_name', 'speaker_relation',
        'loan_taken', 'last_month_payment', 'payee',
        'payment_date', 'payment_mode', 'payment_reason', 'payment_amount'
    ]
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_csv_rows)
    
    # Summary
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("=" * 80)
    print("📊 FINAL SUMMARY")
    print("=" * 80)
    print(f"{Colors.ENDC}")
    
    total_turns = sum(len(r['csv_rows']) for r in all_results)
    total_latency = sum(r['total_latency'] for r in all_results)
    avg_latency = total_latency / total_turns if total_turns > 0 else 0
    
    print(f"Total Calls: {len(CALL_FLOWS)}")
    print(f"Total Turns: {total_turns}")
    print(f"Total Time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print(f"Average Latency: {avg_latency:.2f}s per turn")
    print(f"\n{Colors.OKGREEN}✅ Results saved to: {csv_file}{Colors.ENDC}\n")

if __name__ == "__main__":
    main()

