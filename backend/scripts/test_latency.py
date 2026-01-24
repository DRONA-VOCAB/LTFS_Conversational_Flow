#!/usr/bin/env python3
"""
Quick latency test for Mistral LLM integration
Tests 5 queries and reports timing statistics
"""

import sys
import time
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.llm.mistral_client import call_mistral

# Test queries
test_queries = [
    {
        "name": "Identity Confirmation (English)",
        "prompt": """
User: "Yes, this is Raj speaking"
Context: Customer name is Raj Kumar, asking for identity confirmation
Respond in Hindi and extract identity_confirmed data.
"""
    },
    {
        "name": "Payment Date (Hindi)",
        "prompt": """
User: "मैंने 20 तारीख को 5000 रुपये दिए थे"
Context: Customer is telling about payment
Extract payment_date and payment_amount. Respond in Hindi.
"""
    },
    {
        "name": "No Loan (English)",
        "prompt": """
User: "I didn't take any loan"
Context: Asking about loan status
Extract loan_taken status. Respond in Hindi.
"""
    },
    {
        "name": "Last Month Payment (Hinglish)",
        "prompt": """
User: "Haan ji maine pichhle mahine payment kar diya tha"
Context: Asking about last month payment
Extract last_month_payment. Respond in Hindi.
"""
    },
    {
        "name": "Complex Payment Info",
        "prompt": """
User: "I paid 10000 rupees on 15th January via UPI for EMI"
Context: Detailed payment information
Extract payment_date, payment_amount, payment_mode, payment_reason. Respond in Hindi.
"""
    }
]

def main():
    print("=" * 80)
    print("🔬 MISTRAL LLM LATENCY TEST")
    print("=" * 80)
    print()
    
    latencies = []
    
    for i, test in enumerate(test_queries, 1):
        print(f"[{i}/{len(test_queries)}] Testing: {test['name']}")
        print("-" * 80)
        
        start = time.time()
        try:
            result = call_mistral(test['prompt'])
            elapsed = time.time() - start
            latencies.append(elapsed)
            
            print(f"⏱️  Latency: {elapsed:.2f}s")
            print(f"✅ Status: Success")
            print(f"📝 Bot Response: {result.get('bot_response', 'N/A')[:80]}...")
            print(f"📊 Extracted Data: {result.get('extracted_data', {})}")
            print()
        except Exception as e:
            elapsed = time.time() - start
            print(f"⏱️  Latency: {elapsed:.2f}s")
            print(f"❌ Status: Failed - {e}")
            print()
    
    # Statistics
    if latencies:
        print("=" * 80)
        print("📊 LATENCY STATISTICS")
        print("=" * 80)
        print(f"Min:     {min(latencies):.2f}s")
        print(f"Max:     {max(latencies):.2f}s")
        print(f"Average: {sum(latencies)/len(latencies):.2f}s")
        print(f"Total:   {sum(latencies):.2f}s")
        print(f"Queries: {len(latencies)}")
        print("=" * 80)
        
        # Performance rating
        avg = sum(latencies)/len(latencies)
        if avg < 2:
            rating = "🚀 EXCELLENT"
        elif avg < 5:
            rating = "✅ GOOD"
        elif avg < 10:
            rating = "⚠️  ACCEPTABLE"
        else:
            rating = "❌ SLOW"
        
        print(f"\nPerformance Rating: {rating}")
        print()

if __name__ == "__main__":
    main()

