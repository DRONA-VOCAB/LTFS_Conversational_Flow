#!/usr/bin/env python3
"""
Analyze the conversation quality from the 15-call test matrix CSV
Checks:
1. Bot response quality and relevance
2. Data extraction accuracy
3. Conversation flow coherence
4. LLM understanding issues
"""

import csv
import json
from pathlib import Path
from typing import List, Dict
from collections import defaultdict

# Color codes
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def load_csv_data(csv_path: Path) -> List[Dict]:
    """Load CSV data into a list of dicts"""
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

def group_by_call(data: List[Dict]) -> Dict[str, List[Dict]]:
    """Group rows by call_id"""
    grouped = defaultdict(list)
    for row in data:
        if row.get('call_id'):  # Skip empty rows
            grouped[row['call_id']].append(row)
    return dict(grouped)

def analyze_bot_responses(calls: Dict[str, List[Dict]]) -> Dict:
    """Analyze bot response quality"""
    issues = []
    good_responses = []
    
    for call_id, turns in calls.items():
        for turn in turns:
            bot_response = turn.get('bot_response', '').strip()
            user_response = turn.get('user_response', '').strip()
            turn_num = turn.get('turn')
            
            # Check for empty bot responses
            if not bot_response:
                issues.append({
                    'call_id': call_id,
                    'turn': turn_num,
                    'issue': 'EMPTY_BOT_RESPONSE',
                    'user_said': user_response
                })
            
            # Check for overly long responses (should be 3-12 words)
            elif bot_response:
                word_count = len(bot_response.split())
                if word_count > 20:
                    issues.append({
                        'call_id': call_id,
                        'turn': turn_num,
                        'issue': 'TOO_LONG_RESPONSE',
                        'word_count': word_count,
                        'bot_response': bot_response[:100] + '...'
                    })
                elif word_count <= 12 and bot_response not in ['', 'धन्यवाद']:
                    good_responses.append({
                        'call_id': call_id,
                        'turn': turn_num,
                        'word_count': word_count,
                        'bot_response': bot_response
                    })
    
    return {
        'issues': issues,
        'good_responses': good_responses,
        'total_responses': sum(len(turns) for turns in calls.values()),
        'issue_rate': len(issues) / sum(len(turns) for turns in calls.values()) * 100 if calls else 0
    }

def analyze_data_extraction(calls: Dict[str, List[Dict]]) -> Dict:
    """Analyze data extraction accuracy"""
    extraction_issues = []
    extraction_success = []
    
    fields_to_check = [
        'identity_confirmed', 'speaker_name', 'speaker_relation',
        'loan_taken', 'last_month_payment', 'payee',
        'payment_date', 'payment_mode', 'payment_reason', 'payment_amount'
    ]
    
    for call_id, turns in calls.items():
        extracted_data = {field: None for field in fields_to_check}
        
        for turn in turns:
            turn_num = turn.get('turn')
            user_response = turn.get('user_response', '').strip()
            
            for field in fields_to_check:
                value = turn.get(field, '').strip()
                if value and value != extracted_data[field]:
                    extracted_data[field] = value
                    
                    # Validate extraction logic
                    if field == 'payment_mode':
                        if 'UPI' in user_response or 'upi' in user_response:
                            if value != 'online_lan':
                                extraction_issues.append({
                                    'call_id': call_id,
                                    'turn': turn_num,
                                    'field': field,
                                    'user_said': user_response,
                                    'extracted': value,
                                    'expected': 'online_lan',
                                    'severity': 'MEDIUM'
                                })
                        elif 'NEFT' in user_response or 'RTGS' in user_response:
                            if value != 'online_lan':
                                extraction_issues.append({
                                    'call_id': call_id,
                                    'turn': turn_num,
                                    'field': field,
                                    'user_said': user_response,
                                    'extracted': value,
                                    'expected': 'online_lan',
                                    'severity': 'MEDIUM'
                                })
                        elif 'कैश' in user_response or 'cash' in user_response.lower():
                            if value != 'cash':
                                extraction_issues.append({
                                    'call_id': call_id,
                                    'turn': turn_num,
                                    'field': field,
                                    'user_said': user_response,
                                    'extracted': value,
                                    'expected': 'cash',
                                    'severity': 'HIGH'
                                })
                        elif 'NACH' in user_response or 'ऑटो डेबिट' in user_response:
                            if value != 'nach':
                                extraction_issues.append({
                                    'call_id': call_id,
                                    'turn': turn_num,
                                    'field': field,
                                    'user_said': user_response,
                                    'extracted': value,
                                    'expected': 'nach',
                                    'severity': 'MEDIUM'
                                })
                    
                    elif field == 'payee':
                        if 'खुद' in user_response or 'मैंने' in user_response:
                            if value == 'self':
                                extraction_success.append({
                                    'call_id': call_id,
                                    'turn': turn_num,
                                    'field': field,
                                    'extracted': value
                                })
                        elif 'भाई' in user_response:
                            if value != 'relative':
                                extraction_issues.append({
                                    'call_id': call_id,
                                    'turn': turn_num,
                                    'field': field,
                                    'user_said': user_response,
                                    'extracted': value,
                                    'expected': 'relative',
                                    'severity': 'HIGH'
                                })
                        elif 'दोस्त' in user_response or 'friend' in user_response.lower():
                            if value != 'friend':
                                extraction_issues.append({
                                    'call_id': call_id,
                                    'turn': turn_num,
                                    'field': field,
                                    'user_said': user_response,
                                    'extracted': value,
                                    'expected': 'friend',
                                    'severity': 'HIGH'
                                })
                        elif 'पत्नी' in user_response or 'wife' in user_response.lower():
                            if value != 'relative':
                                extraction_issues.append({
                                    'call_id': call_id,
                                    'turn': turn_num,
                                    'field': field,
                                    'user_said': user_response,
                                    'extracted': value,
                                    'expected': 'relative',
                                    'severity': 'HIGH'
                                })
                    
                    elif field == 'payment_reason':
                        if 'EMI और charges' in user_response or 'EMI aur charges' in user_response:
                            if value != 'emi_charges':
                                extraction_issues.append({
                                    'call_id': call_id,
                                    'turn': turn_num,
                                    'field': field,
                                    'user_said': user_response,
                                    'extracted': value,
                                    'expected': 'emi_charges',
                                    'severity': 'MEDIUM'
                                })
    
    return {
        'extraction_issues': extraction_issues,
        'extraction_success': extraction_success,
        'total_extractions': len(extraction_success) + len(extraction_issues)
    }

def analyze_conversation_flow(calls: Dict[str, List[Dict]]) -> Dict:
    """Analyze conversation flow coherence"""
    flow_issues = []
    good_flows = []
    
    for call_id, turns in calls.items():
        # Check logical progression
        identity_confirmed = False
        loan_confirmed = False
        payment_confirmed = False
        
        for i, turn in enumerate(turns):
            turn_num = turn.get('turn')
            bot_response = turn.get('bot_response', '').strip()
            user_response = turn.get('user_response', '').strip()
            
            # Check if bot is asking for already provided information
            if i > 0:
                prev_turns = turns[:i]
                
                # Check for repetitive questions
                for prev_turn in prev_turns:
                    prev_bot = prev_turn.get('bot_response', '').strip()
                    if prev_bot and bot_response:
                        # Check if bot is asking same question
                        if 'तारीख' in bot_response and 'तारीख' in prev_bot:
                            if turn.get('payment_date'):
                                flow_issues.append({
                                    'call_id': call_id,
                                    'turn': turn_num,
                                    'issue': 'REPETITIVE_QUESTION',
                                    'question': 'payment_date',
                                    'bot_response': bot_response
                                })
                        
                        if 'कौन ने' in bot_response and 'कौन ने' in prev_bot:
                            flow_issues.append({
                                'call_id': call_id,
                                'turn': turn_num,
                                'issue': 'REPETITIVE_QUESTION',
                                'question': 'payee',
                                'bot_response': bot_response
                            })
            
            # Track conversation state
            if turn.get('identity_confirmed') == 'YES':
                identity_confirmed = True
            if turn.get('loan_taken') == 'YES':
                loan_confirmed = True
            if turn.get('last_month_payment') == 'YES':
                payment_confirmed = True
            
            # Check for illogical flow (asking payment details without confirming payment)
            if not payment_confirmed and turn.get('payment_mode'):
                if 'पेमेंट किया' not in user_response and 'payment' not in user_response.lower():
                    flow_issues.append({
                        'call_id': call_id,
                        'turn': turn_num,
                        'issue': 'PREMATURE_PAYMENT_DETAILS',
                        'extracted': 'payment_mode',
                        'context': user_response
                    })
        
        # Check if call reached logical conclusion
        if identity_confirmed and loan_confirmed and len(turns) > 1:
            good_flows.append({
                'call_id': call_id,
                'turns': len(turns),
                'completed_fields': sum(1 for turn in turns for field in ['payment_date', 'payment_mode', 'payment_amount'] if turn.get(field))
            })
    
    return {
        'flow_issues': flow_issues,
        'good_flows': good_flows,
        'total_calls': len(calls)
    }

def analyze_llm_understanding(calls: Dict[str, List[Dict]]) -> Dict:
    """Analyze LLM's understanding of user responses"""
    understanding_issues = []
    
    for call_id, turns in calls.items():
        for turn in turns:
            turn_num = turn.get('turn')
            user_response = turn.get('user_response', '').strip()
            bot_response = turn.get('bot_response', '').strip()
            
            # Check for misunderstandings
            
            # Case 1: User says "नहीं" but bot says "धन्यवाद" (positive acknowledgment)
            if 'नहीं' in user_response and not 'नहीं रहे' in user_response:
                if 'धन्यवाद' in bot_response and 'नहीं' not in bot_response:
                    understanding_issues.append({
                        'call_id': call_id,
                        'turn': turn_num,
                        'issue': 'NEGATIVE_MISUNDERSTOOD_AS_POSITIVE',
                        'user_said': user_response,
                        'bot_said': bot_response,
                        'severity': 'HIGH'
                    })
            
            # Case 2: User provides amount but bot doesn't acknowledge it properly
            if any(word in user_response for word in ['रुपये', 'rupees', 'हजार']):
                amount_extracted = turn.get('payment_amount', '').strip()
                if not amount_extracted:
                    understanding_issues.append({
                        'call_id': call_id,
                        'turn': turn_num,
                        'issue': 'AMOUNT_NOT_EXTRACTED',
                        'user_said': user_response,
                        'severity': 'HIGH'
                    })
            
            # Case 3: User says brother/relative but extracted as third_party
            if 'भाई' in user_response or 'पत्नी' in user_response:
                speaker_relation = turn.get('speaker_relation', '').strip()
                if speaker_relation and speaker_relation not in ['brother', 'relative', 'wife']:
                    understanding_issues.append({
                        'call_id': call_id,
                        'turn': turn_num,
                        'issue': 'RELATIVE_MISCLASSIFIED',
                        'user_said': user_response,
                        'extracted': speaker_relation,
                        'severity': 'HIGH'
                    })
            
            # Case 4: Empty bot response (LLM completely failed)
            if user_response and not bot_response:
                understanding_issues.append({
                    'call_id': call_id,
                    'turn': turn_num,
                    'issue': 'COMPLETE_FAILURE',
                    'user_said': user_response,
                    'severity': 'CRITICAL'
                })
    
    return {
        'understanding_issues': understanding_issues,
        'total_turns': sum(len(turns) for turns in calls.values())
    }

def print_analysis_report(analysis: Dict):
    """Print comprehensive analysis report"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("=" * 100)
    print("📊 CONVERSATION QUALITY ANALYSIS REPORT")
    print("=" * 100)
    print(f"{Colors.ENDC}\n")
    
    # 1. Bot Response Quality
    print(f"{Colors.BOLD}1. BOT RESPONSE QUALITY{Colors.ENDC}")
    print(f"   Total Responses: {analysis['bot_responses']['total_responses']}")
    print(f"   Good Responses (3-12 words): {len(analysis['bot_responses']['good_responses'])}")
    print(f"   Issues Found: {len(analysis['bot_responses']['issues'])}")
    print(f"   Issue Rate: {analysis['bot_responses']['issue_rate']:.1f}%")
    
    if analysis['bot_responses']['issues']:
        print(f"\n   {Colors.WARNING}⚠️  Response Issues:{Colors.ENDC}")
        for i, issue in enumerate(analysis['bot_responses']['issues'][:5], 1):
            print(f"      {i}. {issue['call_id']} Turn {issue['turn']}: {issue['issue']}")
            if 'bot_response' in issue:
                print(f"         Response: {issue['bot_response']}")
    
    # 2. Data Extraction Accuracy
    print(f"\n{Colors.BOLD}2. DATA EXTRACTION ACCURACY{Colors.ENDC}")
    print(f"   Total Extractions: {analysis['data_extraction']['total_extractions']}")
    print(f"   Successful: {len(analysis['data_extraction']['extraction_success'])}")
    print(f"   Issues: {len(analysis['data_extraction']['extraction_issues'])}")
    
    if analysis['data_extraction']['extraction_issues']:
        print(f"\n   {Colors.FAIL}❌ Extraction Issues:{Colors.ENDC}")
        high_severity = [i for i in analysis['data_extraction']['extraction_issues'] if i['severity'] == 'HIGH']
        for i, issue in enumerate(high_severity[:10], 1):
            print(f"      {i}. {issue['call_id']} Turn {issue['turn']}: {issue['field']}")
            print(f"         User: {issue['user_said']}")
            print(f"         Extracted: {issue['extracted']} | Expected: {issue['expected']}")
    
    # 3. Conversation Flow
    print(f"\n{Colors.BOLD}3. CONVERSATION FLOW{Colors.ENDC}")
    print(f"   Total Calls: {analysis['conversation_flow']['total_calls']}")
    print(f"   Good Flows: {len(analysis['conversation_flow']['good_flows'])}")
    print(f"   Flow Issues: {len(analysis['conversation_flow']['flow_issues'])}")
    
    if analysis['conversation_flow']['flow_issues']:
        print(f"\n   {Colors.WARNING}⚠️  Flow Issues:{Colors.ENDC}")
        for i, issue in enumerate(analysis['conversation_flow']['flow_issues'][:5], 1):
            print(f"      {i}. {issue['call_id']} Turn {issue['turn']}: {issue['issue']}")
            if 'bot_response' in issue:
                print(f"         Question: {issue['bot_response'][:80]}")
    
    # 4. LLM Understanding
    print(f"\n{Colors.BOLD}4. LLM UNDERSTANDING{Colors.ENDC}")
    print(f"   Total Turns Analyzed: {analysis['llm_understanding']['total_turns']}")
    print(f"   Understanding Issues: {len(analysis['llm_understanding']['understanding_issues'])}")
    
    critical_issues = [i for i in analysis['llm_understanding']['understanding_issues'] if i['severity'] == 'CRITICAL']
    high_issues = [i for i in analysis['llm_understanding']['understanding_issues'] if i['severity'] == 'HIGH']
    
    print(f"   Critical Issues: {len(critical_issues)}")
    print(f"   High Severity: {len(high_issues)}")
    
    if critical_issues:
        print(f"\n   {Colors.FAIL}🚨 CRITICAL: Complete LLM Failures{Colors.ENDC}")
        for i, issue in enumerate(critical_issues[:5], 1):
            print(f"      {i}. {issue['call_id']} Turn {issue['turn']}")
            print(f"         User: {issue['user_said']}")
    
    if high_issues:
        print(f"\n   {Colors.WARNING}⚠️  HIGH: Misunderstandings{Colors.ENDC}")
        for i, issue in enumerate(high_issues[:10], 1):
            print(f"      {i}. {issue['call_id']} Turn {issue['turn']}: {issue['issue']}")
            print(f"         User: {issue['user_said']}")
            if 'bot_said' in issue:
                print(f"         Bot: {issue['bot_said'][:80]}")
    
    # 5. Overall Assessment
    print(f"\n{Colors.HEADER}{Colors.BOLD}5. OVERALL ASSESSMENT{Colors.ENDC}")
    
    total_issues = (
        len(analysis['bot_responses']['issues']) +
        len(analysis['data_extraction']['extraction_issues']) +
        len(analysis['conversation_flow']['flow_issues']) +
        len(critical_issues)
    )
    
    total_turns = analysis['llm_understanding']['total_turns']
    success_rate = ((total_turns - total_issues) / total_turns * 100) if total_turns > 0 else 0
    
    print(f"   Total Issues: {total_issues}")
    print(f"   Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print(f"   {Colors.OKGREEN}✅ EXCELLENT: LLM is performing very well{Colors.ENDC}")
    elif success_rate >= 75:
        print(f"   {Colors.OKCYAN}✓ GOOD: LLM is performing well with minor issues{Colors.ENDC}")
    elif success_rate >= 60:
        print(f"   {Colors.WARNING}⚠️  MODERATE: LLM needs improvement{Colors.ENDC}")
    else:
        print(f"   {Colors.FAIL}❌ POOR: LLM needs significant improvement{Colors.ENDC}")
    
    print(f"\n{Colors.HEADER}{'=' * 100}{Colors.ENDC}\n")

def main():
    csv_path = Path(__file__).parent.parent.parent / "backend/app/ltfs_mistral_15call.csv"
    
    if not csv_path.exists():
        print(f"{Colors.FAIL}❌ CSV file not found: {csv_path}{Colors.ENDC}")
        return
    
    print(f"{Colors.OKCYAN}Loading data from: {csv_path}{Colors.ENDC}")
    
    data = load_csv_data(csv_path)
    calls = group_by_call(data)
    
    print(f"Loaded {len(calls)} calls with {len(data)} total turns\n")
    
    # Run analyses
    analysis = {
        'bot_responses': analyze_bot_responses(calls),
        'data_extraction': analyze_data_extraction(calls),
        'conversation_flow': analyze_conversation_flow(calls),
        'llm_understanding': analyze_llm_understanding(calls)
    }
    
    # Print report
    print_analysis_report(analysis)
    
    # Save detailed report
    report_path = Path(__file__).parent.parent.parent / "CONVERSATION_QUALITY_REPORT.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    
    print(f"{Colors.OKGREEN}✅ Detailed report saved to: {report_path}{Colors.ENDC}\n")

if __name__ == "__main__":
    main()

