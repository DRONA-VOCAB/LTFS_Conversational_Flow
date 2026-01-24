"""
Detailed quality assessment of Mistral responses
"""
import os
import sys
import json
import time

# Set up environment
os.environ["LLM_PROVIDER"] = "mistral"
os.environ["MISTRAL_USE_API"] = "true"
os.environ["MISTRAL_API_BASE"] = "http://192.168.30.121:5001"
os.environ["MISTRAL_API_KEY"] = "local"

# Add to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from llm.gemini_client import call_gemini

# Test cases with expected quality criteria
test_cases = [
    {
        "name": "Identity Confirmation with Name",
        "prompt": """You are an experienced FEMALE customer service representative from L and T Finance.

Customer said: "हाँ, मैं राज कुमार बोल रहा हूँ"

Respond naturally in Hindi, acknowledging the customer by name.

JSON format:
{
  "bot_response": "natural Hindi response",
  "extracted_data": {"identity_confirmed": "YES"},
  "next_action": "continue",
  "call_end_reason": null
}""",
        "expected_qualities": [
            "Uses customer name (राज कुमार)",
            "Polite and professional tone",
            "Female representative voice",
            "Natural Hindi"
        ]
    },
    {
        "name": "Payment Details Extraction",
        "prompt": """You are an experienced FEMALE customer service representative from L and T Finance.

Customer said: "मैंने 20 जनवरी को ब्रांच में जाकर 10000 रुपये EMI के लिए दिए थे"

Context: Customer राज कुमार has confirmed identity and loan.

Extract ALL payment information and provide natural acknowledgment in Hindi.

JSON format:
{
  "bot_response": "natural Hindi acknowledgment",
  "extracted_data": {
    "payment_date": "20/01/2026",
    "payment_mode": "branch",
    "payment_amount": "10000",
    "payment_reason": "emi"
  },
  "next_action": "continue",
  "call_end_reason": null
}""",
        "expected_qualities": [
            "Extracts all 4 fields correctly",
            "Date in dd/mm/yyyy format",
            "Acknowledges the payment",
            "Professional tone"
        ]
    },
    {
        "name": "Handling Unclear Response",
        "prompt": """You are an experienced FEMALE customer service representative from L and T Finance.

Customer said: "हम्म... मुझे याद नहीं है"

Context: Asked about payment date.

Respond politely asking for clarification.

JSON format:
{
  "bot_response": "polite clarification request in Hindi",
  "extracted_data": {},
  "next_action": "continue",
  "call_end_reason": null
}""",
        "expected_qualities": [
            "Polite clarification request",
            "Offers help or alternatives",
            "Maintains professional tone",
            "Empathetic response"
        ]
    },
    {
        "name": "Customer Wants to Disconnect",
        "prompt": """You are an experienced FEMALE customer service representative from L and T Finance.

Customer said: "मुझे अभी जाना है, बाद में बात करते हैं"

Context: Mid-conversation about payment details.

Respond politely and end call appropriately.

JSON format:
{
  "bot_response": "polite goodbye in Hindi",
  "extracted_data": {},
  "next_action": "end_call",
  "call_end_reason": "customer_busy"
}""",
        "expected_qualities": [
            "Polite goodbye",
            "Sets call_end_reason",
            "next_action is 'end_call'",
            "Professional closing"
        ]
    },
    {
        "name": "Multiple Details in One Response",
        "prompt": """You are an experienced FEMALE customer service representative from L and T Finance.

Customer said: "मैं रवि शर्मा हूँ और मैंने 15 जनवरी को ऑनलाइन 8500 रुपये का पेमेंट किया था EMI के लिए"

Context: First response in conversation.

Extract ALL information and respond naturally.

JSON format:
{
  "bot_response": "natural Hindi response",
  "extracted_data": {
    "identity_confirmed": "YES",
    "payment_date": "15/01/2026",
    "payment_mode": "online_lan",
    "payment_amount": "8500",
    "payment_reason": "emi"
  },
  "next_action": "continue",
  "call_end_reason": null
}""",
        "expected_qualities": [
            "Extracts all 5+ fields",
            "Acknowledges identity AND payment",
            "Natural conversational flow",
            "Complete response"
        ]
    }
]

print("=" * 80)
print("🔍 MISTRAL RESPONSE QUALITY ASSESSMENT")
print("=" * 80)
print(f"Server: http://192.168.30.121:5001")
print(f"Model: Mistral-7B-Instruct-v0.3 (4-bit quantized)")
print("=" * 80)
print()

quality_scores = []

for i, test in enumerate(test_cases, 1):
    print(f"\n{'=' * 80}")
    print(f"TEST {i}/5: {test['name']}")
    print(f"{'=' * 80}")
    
    start_time = time.time()
    
    try:
        result = call_gemini(test['prompt'])
        elapsed = time.time() - start_time
        
        print(f"⏱️  Response Time: {elapsed:.2f}s")
        print()
        
        # Check if valid JSON structure
        is_valid_json = isinstance(result, dict)
        has_bot_response = 'bot_response' in result
        
        print("📋 RESPONSE STRUCTURE:")
        print(f"  ✓ Valid JSON: {is_valid_json}")
        print(f"  ✓ Has bot_response: {has_bot_response}")
        if 'extracted_data' in result:
            print(f"  ✓ Has extracted_data: True")
        if 'next_action' in result:
            print(f"  ✓ Has next_action: {result.get('next_action')}")
        if 'call_end_reason' in result:
            print(f"  ✓ Has call_end_reason: {result.get('call_end_reason')}")
        
        print()
        print("💬 BOT RESPONSE:")
        if has_bot_response:
            bot_resp = result['bot_response']
            print(f"  \"{bot_resp}\"")
            print(f"  Length: {len(bot_resp)} characters")
        else:
            print("  ❌ No bot_response field!")
        
        print()
        print("📊 EXTRACTED DATA:")
        if 'extracted_data' in result:
            extracted = result['extracted_data']
            if extracted:
                for key, value in extracted.items():
                    print(f"  • {key}: {value}")
            else:
                print("  (empty)")
        else:
            # Sometimes data is at root level
            print("  Data at root level:")
            for key, value in result.items():
                if key not in ['bot_response', 'next_action', 'call_end_reason']:
                    print(f"  • {key}: {value}")
        
        print()
        print("✅ QUALITY CHECKLIST:")
        for quality in test['expected_qualities']:
            print(f"  • {quality}")
        
        # Calculate quality score
        score = 0
        max_score = 5
        
        # 1. Valid JSON structure
        if is_valid_json:
            score += 1
        
        # 2. Has bot_response
        if has_bot_response:
            score += 1
        
        # 3. Bot response is not empty and reasonable length
        if has_bot_response and len(result.get('bot_response', '')) > 10:
            score += 1
        
        # 4. Has extracted_data or data fields
        if 'extracted_data' in result or len(result) > 2:
            score += 1
        
        # 5. Response time is reasonable (< 5s)
        if elapsed < 5.0:
            score += 1
        
        quality_scores.append({
            'test': test['name'],
            'score': score,
            'max_score': max_score,
            'time': elapsed,
            'result': result
        })
        
        print()
        print(f"🎯 Quality Score: {score}/{max_score} ({score/max_score*100:.0f}%)")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        quality_scores.append({
            'test': test['name'],
            'score': 0,
            'max_score': 5,
            'time': 0,
            'error': str(e)
        })

# Overall Summary
print(f"\n{'=' * 80}")
print("📈 OVERALL QUALITY ASSESSMENT")
print(f"{'=' * 80}")

total_score = sum(q['score'] for q in quality_scores)
max_total = sum(q['max_score'] for q in quality_scores)
avg_time = sum(q['time'] for q in quality_scores if 'time' in q) / len(quality_scores)

print(f"Overall Quality Score: {total_score}/{max_total} ({total_score/max_total*100:.1f}%)")
print(f"Average Response Time: {avg_time:.2f}s")
print()

# Quality breakdown
for q in quality_scores:
    status = "✅" if q['score'] >= q['max_score'] * 0.8 else "⚠️" if q['score'] >= q['max_score'] * 0.6 else "❌"
    print(f"{status} {q['test']}: {q['score']}/{q['max_score']} ({q['time']:.2f}s)")

print(f"\n{'=' * 80}")
print("🏆 VERDICT:")
if total_score >= max_total * 0.9:
    print("🌟 EXCELLENT - High quality responses with 4-bit quantization!")
elif total_score >= max_total * 0.75:
    print("👍 GOOD - Quality responses, minor improvements possible")
elif total_score >= max_total * 0.6:
    print("⚠️  ACCEPTABLE - Some quality issues detected")
else:
    print("❌ POOR - Significant quality issues")
print(f"{'=' * 80}")

