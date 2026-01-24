"""
Test script to verify Mistral integration with 10 different queries
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

# Test queries representing different conversation stages
test_queries = [
    {
        "name": "Identity Confirmation - Yes",
        "prompt": """
Customer said: "हाँ, मैं राज कुमार बोल रहा हूँ"

Extract information and respond in JSON:
{
  "bot_response": "response in Hindi",
  "extracted_data": {"identity_confirmed": "YES"},
  "next_action": "continue",
  "call_end_reason": null
}
"""
    },
    {
        "name": "Identity Confirmation - Wrong Person",
        "prompt": """
Customer said: "नहीं, मैं उनका भाई हूँ"

Extract information and respond in JSON:
{
  "bot_response": "response in Hindi",
  "extracted_data": {"identity_confirmed": "NO"},
  "next_action": "continue",
  "call_end_reason": null
}
"""
    },
    {
        "name": "Loan Confirmation - Yes",
        "prompt": """
Customer said: "हाँ, मैंने लोन लिया है"

Extract information and respond in JSON:
{
  "bot_response": "response in Hindi",
  "extracted_data": {"loan_taken": "YES"},
  "next_action": "continue",
  "call_end_reason": null
}
"""
    },
    {
        "name": "Payment Confirmation - Yes",
        "prompt": """
Customer said: "हाँ, मैंने पिछले महीने पेमेंट किया था"

Extract information and respond in JSON:
{
  "bot_response": "response in Hindi",
  "extracted_data": {"last_month_payment": "YES"},
  "next_action": "continue",
  "call_end_reason": null
}
"""
    },
    {
        "name": "Payment Details",
        "prompt": """
Customer said: "मैंने 15 तारीख को ऑनलाइन 5000 रुपये का पेमेंट किया था"

Extract information and respond in JSON:
{
  "bot_response": "response in Hindi",
  "extracted_data": {
    "payment_date": "15/01/2026",
    "payment_mode": "online_lan",
    "payment_amount": "5000"
  },
  "next_action": "continue",
  "call_end_reason": null
}
"""
    },
    {
        "name": "Payee Information - Self",
        "prompt": """
Customer said: "मैंने खुद पेमेंट किया था"

Extract information and respond in JSON:
{
  "bot_response": "response in Hindi",
  "extracted_data": {"payee": "self"},
  "next_action": "continue",
  "call_end_reason": null
}
"""
    },
    {
        "name": "Payment Reason - EMI",
        "prompt": """
Customer said: "मैंने EMI के लिए पेमेंट किया था"

Extract information and respond in JSON:
{
  "bot_response": "response in Hindi",
  "extracted_data": {"payment_reason": "emi"},
  "next_action": "continue",
  "call_end_reason": null
}
"""
    },
    {
        "name": "Unclear Response",
        "prompt": """
Customer said: "हम्म... पता नहीं"

Extract information and respond in JSON:
{
  "bot_response": "response in Hindi asking to clarify",
  "extracted_data": {},
  "next_action": "continue",
  "call_end_reason": null
}
"""
    },
    {
        "name": "Multiple Information",
        "prompt": """
Customer said: "मैंने 20 जनवरी को ब्रांच में जाकर 10000 रुपये EMI के लिए दिए थे"

Extract information and respond in JSON:
{
  "bot_response": "response in Hindi",
  "extracted_data": {
    "payment_date": "20/01/2026",
    "payment_mode": "branch",
    "payment_amount": "10000",
    "payment_reason": "emi"
  },
  "next_action": "continue",
  "call_end_reason": null
}
"""
    },
    {
        "name": "Confirmation - Yes",
        "prompt": """
Customer said: "हाँ, सब सही है"

This is a confirmation response. Respond in JSON:
{
  "bot_response": "response in Hindi",
  "extracted_data": {},
  "next_action": "summary",
  "call_end_reason": null
}
"""
    }
]

print("=" * 80)
print("MISTRAL INTEGRATION TEST - 10 QUERIES")
print("=" * 80)
print(f"API Endpoint: http://192.168.30.121:5001")
print(f"LLM Provider: mistral")
print("=" * 80)
print()

results = []
total_time = 0

for i, query in enumerate(test_queries, 1):
    print(f"\n{'=' * 80}")
    print(f"TEST {i}/10: {query['name']}")
    print(f"{'=' * 80}")
    
    start_time = time.time()
    
    try:
        result = call_gemini(query['prompt'])
        elapsed = time.time() - start_time
        total_time += elapsed
        
        success = isinstance(result, dict) and len(result) > 1
        
        results.append({
            "test": query['name'],
            "success": success,
            "time": elapsed,
            "result": result
        })
        
        if success:
            print(f"✅ SUCCESS ({elapsed:.2f}s)")
            print(f"Keys: {list(result.keys())}")
            if 'bot_response' in result:
                print(f"Bot Response: {result['bot_response'][:100]}...")
            if 'extracted_data' in result and result['extracted_data']:
                print(f"Extracted Data: {json.dumps(result['extracted_data'], ensure_ascii=False)}")
        else:
            print(f"❌ FAILED ({elapsed:.2f}s)")
            print(f"Result: {result}")
            
    except Exception as e:
        elapsed = time.time() - start_time
        total_time += elapsed
        results.append({
            "test": query['name'],
            "success": False,
            "time": elapsed,
            "error": str(e)
        })
        print(f"❌ ERROR ({elapsed:.2f}s): {e}")

# Summary
print(f"\n{'=' * 80}")
print("SUMMARY")
print(f"{'=' * 80}")

successes = sum(1 for r in results if r['success'])
failures = len(results) - successes
avg_time = total_time / len(results) if results else 0

print(f"Total Tests: {len(results)}")
print(f"✅ Successful: {successes}")
print(f"❌ Failed: {failures}")
print(f"⏱️  Average Time: {avg_time:.2f}s")
print(f"⏱️  Total Time: {total_time:.2f}s")
print(f"Success Rate: {(successes/len(results)*100):.1f}%")

# Show failed tests
if failures > 0:
    print(f"\n{'=' * 80}")
    print("FAILED TESTS:")
    print(f"{'=' * 80}")
    for r in results:
        if not r['success']:
            print(f"❌ {r['test']}")
            if 'error' in r:
                print(f"   Error: {r['error']}")
            else:
                print(f"   Result: {r.get('result', 'N/A')}")

print(f"\n{'=' * 80}")

