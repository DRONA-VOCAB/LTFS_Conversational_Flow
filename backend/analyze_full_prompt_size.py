#!/usr/bin/env python3
"""
Analyze the full prompt size including context added per turn
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.config.prompt import PROMPT as CONVERSATIONAL_PROMPT

def count_tokens_tiktoken(text: str) -> int:
    """Count tokens using tiktoken"""
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except ImportError:
        try:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "tiktoken", "-q"])
            import tiktoken
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except:
            return int(len(text) / 3.5)  # Rough estimate

# Sample context that gets added per turn
sample_context = """
    CURRENT CONVERSATION CONTEXT:
    - Customer Name: राम कुमार शर्मा
    - Conversation Stage: payment_date_collection
    - Current Data Collected: {'identity_confirmed': 'YES', 'loan_taken': 'YES', 'last_month_payment': 'YES', 'payee': 'self', 'payment_date': None, 'payment_mode': None, 'payment_reason': None, 'payment_amount': None}
    - Missing Information: ['payment date', 'payment method', 'payment reason', 'payment amount']
    - Last Bot Response: आपने कब payment किया था?

    CUSTOMER'S RESPONSE: "मैंने पिछले महीने 15 तारीख को payment किया था, online UPI से, ₹5000 का"

    ANALYSIS REQUIRED:
    1. What type of response is this? (clear answer, unclear, irrelevant, rude, confused, partial, etc.)
    2. What information can be extracted from this response?
    3. How should I acknowledge their response?
    4. What should I ask next or how should I redirect?
    5. What tone should I use based on their response?

    REMEMBER:
    - ALWAYS acknowledge what they said first
    - Be patient and understanding regardless of their response type
    - Extract ANY useful information mentioned
    - Handle difficult customers with empathy
    - Keep the conversation natural and human-like
    - Don't repeat questions unnecessarily if information is already provided

    Based on the customer's response and current context, provide your response:
    """

# Also check the date instruction that gets added in gemini_client.py
date_instruction = """
IMPORTANT DATE RULES:
- Current year is 2026
- When processing dates, ALWAYS use 2026 as the year unless explicitly told otherwise
- NEVER use years like 2025, 2024, 2023, or any year before 2026
"""

json_instruction = """

CRITICAL OUTPUT REQUIREMENTS:
1. You MUST respond with ONLY a valid JSON object
2. Do NOT include any explanations, reasoning, or text before or after the JSON
3. Do NOT use markdown code blocks (no ```json or ```)
4. Start your response immediately with { and end with }
5. Do NOT include any special tokens like <|return|> or <return>
6. If you need to think, do it silently - only output the final JSON

Example of CORRECT output:
{"key": "value"}

Example of INCORRECT output:
We need to output JSON. {"key": "value"} This is the answer.
"""

base_prompt_tokens = count_tokens_tiktoken(CONVERSATIONAL_PROMPT)
context_tokens = count_tokens_tiktoken(sample_context)
date_instruction_tokens = count_tokens_tiktoken(date_instruction)
json_instruction_tokens = count_tokens_tiktoken(json_instruction)

full_prompt_tokens = base_prompt_tokens + context_tokens + date_instruction_tokens + json_instruction_tokens

print("=" * 70)
print("FULL PROMPT SIZE ANALYSIS (per turn)")
print("=" * 70)
print()
print(f"Base prompt (CONVERSATIONAL_PROMPT): {base_prompt_tokens:,} tokens")
print(f"Date instruction (from gemini_client): {date_instruction_tokens:,} tokens")
print(f"Context per turn (sample): {context_tokens:,} tokens")
print(f"JSON instruction (from gemini_client): {json_instruction_tokens:,} tokens")
print(f"{'─' * 70}")
print(f"TOTAL PER TURN: ~{full_prompt_tokens:,} tokens")
print()

# Calculate with different context sizes
print("CONTEXT WINDOW ANALYSIS:")
print()
context_windows = {
    "4K (4096)": 4096,
    "8K (8192)": 8192,
    "16K (16384)": 16384,
}

for name, window in context_windows.items():
    remaining = window - full_prompt_tokens
    percentage = (full_prompt_tokens / window) * 100
    status = "✓ OK" if remaining > 500 else "⚠️ TIGHT" if remaining > 0 else "✗ EXCEEDED"
    print(f"{name:15s} → {remaining:6,} tokens remaining ({percentage:5.1f}% used) {status}")

print()
print("RECOMMENDATIONS:")
print()
if full_prompt_tokens > 3500:
    print("⚠️  WARNING: Full prompt is very large (>3500 tokens)")
    print("   - 4K context window will be VERY tight")
    print("   - Recommend using 8K or higher")
    print("   - With 4K, you may hit context limits on longer conversations")
elif full_prompt_tokens > 3000:
    print("⚠️  CAUTION: Full prompt is large (>3000 tokens)")
    print("   - 4K context window will be tight but workable")
    print("   - 8K is recommended for safety margin")
    print("   - Monitor for context overflow errors")
else:
    print("✓ Full prompt size is reasonable")
    print("   - 4K should work, but 8K provides better safety margin")

print()
print("NOTE: Context size varies per turn based on:")
print("   - Customer name length")
print("   - Amount of collected data")
print("   - User input length")
print("   - Session state complexity")
print("=" * 70)
