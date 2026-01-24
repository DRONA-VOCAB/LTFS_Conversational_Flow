"""
LLM client module.

This project historically used Google Gemini via `google-generativeai`.
We now use a locally hosted OpenAI-compatible GPT-OSS endpoint.

Supports multiple LLM providers:
- GPT-OSS (default): OpenAI-compatible API endpoint
- Mistral: Direct inference or API-based
- Gemini: Google Gemini API

Compatibility:
- Keeps `call_gemini(prompt) -> dict` used across question handlers.
- Exposes `model.generate_content(prompt)` used by `summary_service.py`.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


def _normalize_api_base(raw: str) -> str:
    raw = (raw or "").strip().rstrip("/")
    if not raw:
        return "http://192.168.30.132:8001/v1"
    return raw if raw.endswith("/v1") else f"{raw}/v1"


# LLM Provider selection
# Default to Mistral API running at 192.168.30.121:5001 unless overridden by env
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mistral").lower()  # Options: gpt-oss, mistral, gemini

# GPT-OSS configuration
GPT_OSS_MODEL = os.getenv("GPT_OSS_MODEL", "openai/gpt-oss-20b")
GPT_OSS_API_KEY = os.getenv("GPT_OSS_API_KEY", "local")
# User-provided endpoint example: http://192.168.30.132:8001/
GPT_OSS_API_BASE = _normalize_api_base(os.getenv("GPT_OSS_API_BASE", "http://192.168.30.132:8001/"))


@dataclass
class _LLMResponse:
    text: str


def _chat_completion(
    prompt: str, 
    *, 
    temperature: float = 0.1, 
    timeout_s: float = 30.0,
    require_json: bool = False
) -> str:
    url = f"{GPT_OSS_API_BASE}/chat/completions"
    headers = {"Authorization": f"Bearer {GPT_OSS_API_KEY}"}
    
    messages = []
    if require_json:
        # Use system message to enforce JSON output
        messages.append({
            "role": "system",
            "content": "You are a JSON-only response generator. You MUST respond with ONLY valid JSON. Do not include any explanations, markdown, or text outside the JSON object. Start your response with { and end with }."
        })
    
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": GPT_OSS_MODEL,
        "messages": messages,
        "temperature": temperature,
    }

    with httpx.Client(timeout=timeout_s) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = (choices[0] or {}).get("message") or {}
    content = (msg.get("content") or "").strip()
    
    # Strip special tokens that GPT-OSS models sometimes include
    content = re.sub(r'<\|[^|]+\|>', '', content)  # Remove <|token|> patterns
    content = re.sub(r'<return>', '', content, flags=re.IGNORECASE)
    
    return content


class _ModelCompat:
    """Gemini-like wrapper used by existing code (`model.generate_content`)."""

    def generate_content(self, prompt: str, generation_config: Optional[Dict[str, Any]] = None) -> _LLMResponse:
        temperature = 0.1
        if generation_config and isinstance(generation_config, dict):
            temperature = float(generation_config.get("temperature", temperature))
        
        # Route to appropriate provider for summary generation
        if LLM_PROVIDER == "mistral":
            try:
                from llm.mistral_client import _chat_completion as mistral_chat
                text = mistral_chat(prompt, temperature=temperature, require_json=False)
                return _LLMResponse(text=text)
            except (ImportError, Exception) as e:
                print(f"Warning: Mistral not available for summary: {e}, using GPT-OSS")
                # Fall through to GPT-OSS
        
        # Default to GPT-OSS
        # For summary service, we don't require JSON (it returns plain text)
        return _LLMResponse(text=_chat_completion(prompt, temperature=temperature, require_json=False))


# Exported symbol used by `backend/app/services/summary_service.py`
model = _ModelCompat()


def extract_json_from_text(text: str) -> str:
    """Extract JSON from text, handling markdown code blocks, explanations, and special tokens"""
    if not text:
        return ""
    
    # Strip special tokens first
    text = re.sub(r'<\|[^|]+\|>', '', text)  # Remove <|token|> patterns
    text = re.sub(r'<return>', '', text, flags=re.IGNORECASE)
    text = text.strip()
    
    # Try to find JSON in markdown code blocks first
    # Find code block markers and extract content between them
    code_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    # Use a more sophisticated approach: find the code block, then extract JSON properly
    code_block_match = re.search(r'```(?:json)?\s*', text, re.IGNORECASE)
    if code_block_match:
        # Find the start of JSON after the code block marker
        start_pos = code_block_match.end()
        # Find the closing ``` 
        end_marker = text.find('```', start_pos)
        if end_marker > start_pos:
            # Extract content between markers
            code_content = text[start_pos:end_marker].strip()
            # Now extract JSON from this content using proper brace matching
            if code_content.startswith('{'):
                # Use brace matching to find complete JSON
                brace_count = 0
                json_end = -1
                for i, char in enumerate(code_content):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                if json_end > 0:
                    candidate = code_content[:json_end]
                    try:
                        json.loads(candidate)  # Validate
                        return candidate
                    except json.JSONDecodeError:
                        pass
    
    # Find all potential JSON objects (starting with {)
    json_candidates = []
    start_idx = 0
    
    while True:
        start_idx = text.find('{', start_idx)
        if start_idx == -1:
            break
        
        # Count braces to find the matching closing brace
        brace_count = 0
        in_string = False
        escape_next = False
        found_json = False
        
        for i in range(start_idx, len(text)):
            char = text[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Found matching closing brace
                        candidate = text[start_idx:i+1]
                        # Validate it's likely JSON by checking for common JSON patterns
                        if '"' in candidate and (':' in candidate or candidate.count('{') == candidate.count('}')):
                            json_candidates.append((start_idx, candidate))
                            found_json = True
                        break
        
        if not found_json:
            start_idx += 1
        else:
            start_idx = start_idx + len(json_candidates[-1][1])
    
    # Return the longest valid JSON candidate (most likely to be complete)
    if json_candidates:
        # Sort by length (longest first) and return the first valid one
        json_candidates.sort(key=lambda x: len(x[1]), reverse=True)
        for _, candidate in json_candidates:
            # Quick validation: try to parse it
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue
    
    # Fallback: try simple regex if brace matching fails
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if json_match:
        return json_match.group(0)
    
    # Last resort: return text if it starts with { (might be incomplete JSON)
    if text.startswith('{'):
        return text
    
    return ""


def call_gemini(prompt: str) -> dict:
    """Main LLM call function - routes to appropriate provider"""
    # Route to appropriate provider
    if LLM_PROVIDER == "mistral":
        try:
            from llm.mistral_client import call_mistral
            return call_mistral(prompt)
        except ImportError as e:
            print(f"Warning: Mistral client not available: {e}")
            print("Falling back to GPT-OSS")
            # Fall through to GPT-OSS
        except Exception as e:
            print(f"Error calling Mistral: {e}")
            print("Falling back to GPT-OSS")
            # Fall through to GPT-OSS
    
    # Default to GPT-OSS
    response = None
    try:
        # Add date handling instructions to the prompt
        date_instruction = """
IMPORTANT DATE RULES:
- Current year is 2026
- When processing dates, ALWAYS use 2026 as the year unless explicitly told otherwise
- NEVER use years like 2025, 2024, 2023, or any year before 2026
"""
        
        # Enhance prompt with strict JSON requirement
        enhanced_prompt = date_instruction + "\n\n" + prompt + """

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
        
        # Use temperature to encourage structured output
        generation_config = {
            "temperature": 0.1,  # Lower temperature for more consistent output
        }

        # Call with require_json flag to use system message
        raw_response = _chat_completion(enhanced_prompt, temperature=0.1, require_json=True)
        
        if not raw_response:
            print("Warning: Empty response from LLM")
            return {"value": "UNCLEAR", "is_clear": False}
        
        # Extract JSON from response (handles cases where model still adds text)
        json_text = extract_json_from_text(raw_response)
        
        if not json_text:
            print(f"Warning: No JSON found in response. First 200 chars: {raw_response[:200]}")
            return {"value": "UNCLEAR", "is_clear": False}
        
        # Parse JSON with better error handling
        try:
            result = json.loads(json_text)
            return result
        except json.JSONDecodeError as json_err:
            # Try to fix common JSON issues
            # Remove trailing commas
            json_text = re.sub(r',\s*}', '}', json_text)
            json_text = re.sub(r',\s*]', ']', json_text)
            try:
                result = json.loads(json_text)
                return result
            except json.JSONDecodeError:
                print(f"JSON Decode Error: {json_err}")
                print(f"Extracted JSON text (first 500 chars): {json_text[:500]}")
                return {"value": "UNCLEAR", "is_clear": False}
        
    except Exception as e:
        print(f"Error calling LLM: {e}")
        import traceback
        traceback.print_exc()
        return {"value": "UNCLEAR", "is_clear": False}
