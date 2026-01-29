"""
Mistral-7B-Instruct-v0.3 client module.

Supports both:
1. Direct inference using transformers library
2. API-based inference (OpenAI-compatible endpoint)

Usage:
- Set LLM_PROVIDER="mistral" in .env
- For direct inference: Set MISTRAL_MODEL_PATH (optional, defaults to ~/mistral_models/7B-Instruct-v0.3)
- For API inference: Set MISTRAL_API_BASE (e.g., http://localhost:8000/v1)
"""

from __future__ import annotations

import json
import os
import re
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import transformers, but make it optional
TRANSFORMERS_AVAILABLE = False
TORCH_AVAILABLE = False
try:
    import torch
    TORCH_AVAILABLE = True
    from transformers import AutoTokenizer, AutoModelForCausalLM
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    logger.warning("transformers/torch not available. Install with: pip install transformers torch")

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx not available. Install with: pip install httpx")


# Configuration
MISTRAL_MODEL_PATH = os.getenv("MISTRAL_MODEL_PATH", str(Path.home().joinpath("mistral_models", "7B-Instruct-v0.3")))
MISTRAL_API_BASE = os.getenv("MISTRAL_API_BASE", "http://192.168.30.121:5001")  # Default to IP:port 5001
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "local")
MISTRAL_USE_API = os.getenv("MISTRAL_USE_API", "true").lower() == "true"  # Default to API mode
if TORCH_AVAILABLE:
    import torch
    MISTRAL_DEVICE = os.getenv("MISTRAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
else:
    MISTRAL_DEVICE = os.getenv("MISTRAL_DEVICE", "cpu")

# Global model and tokenizer (loaded once)
_model = None
_tokenizer = None

# Strict JSON system prompt for API and direct inference
JSON_SYSTEM_PROMPT = (
    "You are a strict JSON-only response generator for a customer service system.\n\n"
    "🔴 CRITICAL JSON OUTPUT RULES (VIOLATION = SYSTEM FAILURE):\n\n"
    "1. OUTPUT FORMAT:\n"
    "   - MUST start with '{' (opening brace) as the FIRST character\n"
    "   - MUST end with '}' (closing brace) as the LAST character\n"
    "   - NO text, explanations, or comments before or after the JSON\n"
    "   - NO markdown code blocks (NEVER use ```json or ```)\n"
    "   - NO special tokens like <|return|>, <return>, or similar\n\n"
    "2. REQUIRED FIELDS (ALL MUST BE PRESENT):\n"
    "   - \"bot_response\": string (natural Hindi response to customer)\n"
    "   - \"extracted_data\": object (data extracted from customer, can be empty {})\n"
    "   - \"next_action\": string (one of: continue, summary, end_call)\n"
    "   - \"call_end_reason\": string or null (reason if ending call)\n\n"
    "3. BOT_RESPONSE GENERATION RULES:\n"
    "   - ALWAYS generate a natural, contextual Hindi response\n"
    "   - Acknowledge what the customer said\n"
    "   - If extracting data, acknowledge the specific information received\n"
    "   - Use professional but friendly tone\n"
    "   - Keep responses concise (1-2 sentences)\n"
    "   - Examples:\n"
    "     * Customer confirms identity: \"धन्यवाद, [name] जी\"\n"
    "     * Customer gives payment info: \"जी, मैं समझ गई। आपने [amount] रुपये [date] को [mode] से दिए थे\"\n"
    "     * Customer unclear: \"कृपया मुझे थोड़ा और बताएं\"\n\n"
    "4. STRUCTURE EXAMPLES:\n\n"
    "   ✅ CORRECT (complete with contextual response):\n"
    "   {\"bot_response\": \"धन्यवाद राज जी, मैं आपकी पहचान की पुष्टि कर चुकी हूँ\", \"extracted_data\": {\"identity_confirmed\": \"YES\"}, \"next_action\": \"continue\", \"call_end_reason\": null}\n\n"
    "   ✅ CORRECT (payment acknowledgment):\n"
    "   {\"bot_response\": \"जी समझ गई, आपने 20 जनवरी को ब्रांच में 10000 रुपये EMI के लिए दिए थे\", \"extracted_data\": {\"payment_date\": \"20/01/2026\", \"payment_mode\": \"branch\", \"payment_amount\": \"10000\", \"payment_reason\": \"emi\"}, \"next_action\": \"continue\", \"call_end_reason\": null}\n\n"
    "   ✅ CORRECT (empty extracted_data):\n"
    "   {\"bot_response\": \"नमस्ते\", \"extracted_data\": {}, \"next_action\": \"continue\", \"call_end_reason\": null}\n\n"
    "   ❌ INCORRECT (missing bot_response):\n"
    "   {\"payment_date\": \"20/01/2026\", \"payment_amount\": \"5000\"}\n\n"
    "   ❌ INCORRECT (data at root level):\n"
    "   {\"bot_response\": \"hi\", \"payment_date\": \"20/01/2026\"}\n\n"
    "   ❌ INCORRECT (has text before JSON):\n"
    "   Here is the response: {\"bot_response\": \"hello\"}\n\n"
    "5. DATA EXTRACTION RULES:\n"
    "   - Put ALL extracted customer data inside \"extracted_data\" object\n"
    "   - NEVER put extracted data at root level of JSON\n"
    "   - If no data to extract, use empty object: \"extracted_data\": {}\n"
    "   - Common fields: identity_confirmed, loan_taken, payment_date, payment_mode, payment_amount, payment_reason, payee\n\n"
    "6. VALIDATION:\n"
    "   - Your output MUST be parseable by json.loads() in Python\n"
    "   - Must have exactly 4 fields: bot_response, extracted_data, next_action, call_end_reason\n"
    "   - bot_response MUST NOT be empty\n"
    "   - Test your JSON mentally before responding\n\n"
    "⚠️ REMEMBER: Generate COMPLETE responses with ALL 4 fields. The bot_response should acknowledge what the customer said!"
)


@dataclass
class _LLMResponse:
    text: str


def _load_model_direct():
    """Load Mistral model directly using transformers"""
    global _model, _tokenizer
    
    if not TRANSFORMERS_AVAILABLE:
        raise ImportError("transformers library is required for direct inference")
    
    if not TORCH_AVAILABLE:
        raise ImportError("torch library is required for direct inference")
    
    import torch  # Import here to ensure it's available
    
    if _model is not None and _tokenizer is not None:
        return _model, _tokenizer
    
    model_path = Path(MISTRAL_MODEL_PATH)
    
    # Check if model files exist
    if not model_path.exists():
        logger.warning(f"Model path {model_path} does not exist. Trying Hugging Face model ID...")
        model_id = "mistralai/Mistral-7B-Instruct-v0.3"
        logger.info(f"Loading model from Hugging Face: {model_id}")
        _tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        _model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.float16 if MISTRAL_DEVICE == "cuda" else torch.float32,
            device_map="auto" if MISTRAL_DEVICE == "cuda" else None,
            trust_remote_code=True
        )
        if MISTRAL_DEVICE == "cpu":
            _model = _model.to(MISTRAL_DEVICE)
    else:
        logger.info(f"Loading model from local path: {model_path}")
        _tokenizer = AutoTokenizer.from_pretrained(str(model_path), trust_remote_code=True)
        _model = AutoModelForCausalLM.from_pretrained(
            str(model_path),
            torch_dtype=torch.float16 if MISTRAL_DEVICE == "cuda" else torch.float32,
            device_map="auto" if MISTRAL_DEVICE == "cuda" else None,
            trust_remote_code=True
        )
        if MISTRAL_DEVICE == "cpu":
            _model = _model.to(MISTRAL_DEVICE)
    
    _model.eval()
    logger.info(f"✅ Mistral model loaded on {MISTRAL_DEVICE}")
    return _model, _tokenizer


def _chat_completion_api(
    prompt: str,
    temperature: float = 0.1,
    timeout_s: float = 60.0,
    require_json: bool = False,
 ) -> str:
    """Call Mistral via OpenAI-compatible API"""
    if not HTTPX_AVAILABLE:
        raise ImportError("httpx library is required for API inference")
    
    api_base = MISTRAL_API_BASE.rstrip("/")
    if not api_base.endswith("/v1"):
        api_base = f"{api_base}/v1"
    
    url = f"{api_base}/chat/completions"
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}"}
    
    messages = []
    if require_json:
        messages.append({"role": "system", "content": JSON_SYSTEM_PROMPT})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": "mistral-7b-instruct",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 150,  # Reduced from 2048 to force concise responses
    }
    
    start_time = time.time()
    with httpx.Client(timeout=timeout_s) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    elapsed = time.time() - start_time
    logger.info(f"⏱️  Mistral API latency: {elapsed:.2f}s")
    
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = (choices[0] or {}).get("message") or {}
    content = (msg.get("content") or "").strip()
    
    # Strip special tokens
    content = re.sub(r'<\|[^|]+\|>', '', content)
    content = re.sub(r'<return>', '', content, flags=re.IGNORECASE)
    
    return content


def _chat_completion_direct(
    prompt: str,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    require_json: bool = False,
 ) -> str:
    """Call Mistral model directly using transformers"""
    import torch  # Import here to ensure it's available
    
    model, tokenizer = _load_model_direct()
    
    # Format prompt for Mistral Instruct format
    if require_json:
        formatted_prompt = f"<s>[INST] {JSON_SYSTEM_PROMPT}\n\n{prompt} [/INST]"
    else:
        formatted_prompt = f"<s>[INST] {prompt} [/INST]"
    
    # Tokenize
    inputs = tokenizer(formatted_prompt, return_tensors="pt").to(MISTRAL_DEVICE)
    
    # Generate
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
            top_p=0.95,
            pad_token_id=tokenizer.eos_token_id,
        )
    
    # Decode
    generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # Extract response (remove the prompt part)
    if "[/INST]" in generated_text:
        response = generated_text.split("[/INST]")[-1].strip()
    else:
        response = generated_text[len(formatted_prompt):].strip()
    
    return response


def _chat_completion(
    prompt: str,
    temperature: float = 0.1,
    timeout_s: float = 60.0,
    require_json: bool = False,
 ) -> str:
    """Main chat completion function - routes to API or direct inference"""
    if MISTRAL_USE_API and MISTRAL_API_BASE:
        return _chat_completion_api(prompt, temperature, timeout_s, require_json=require_json)
    else:
        return _chat_completion_direct(prompt, temperature, require_json=require_json)


def extract_json_from_text(text: str) -> str:
    """Extract JSON from text, handling markdown code blocks, explanations, and special tokens"""
    if not text:
        return ""
    
    # Strip special tokens first
    text = re.sub(r'<\|[^|]+\|>', '', text)
    text = re.sub(r'<return>', '', text, flags=re.IGNORECASE)
    text = text.strip()
    
    # Try to find JSON in markdown code blocks first
    code_block_match = re.search(r'```(?:json)?\s*', text, re.IGNORECASE)
    if code_block_match:
        start_pos = code_block_match.end()
        end_marker = text.find('```', start_pos)
        if end_marker > start_pos:
            code_content = text[start_pos:end_marker].strip()
            if code_content.startswith('{'):
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
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        pass
    
    # Find all potential JSON objects
    json_candidates = []
    start_idx = 0
    
    while True:
        start_idx = text.find('{', start_idx)
        if start_idx == -1:
            break
        
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
                        candidate = text[start_idx:i+1]
                        if '"' in candidate and (':' in candidate or candidate.count('{') == candidate.count('}')):
                            json_candidates.append((start_idx, candidate))
                            found_json = True
                        break
        
        if not found_json:
            start_idx += 1
        else:
            start_idx = start_idx + len(json_candidates[-1][1])
    
    # Return the longest valid JSON candidate, but check if it's complete
    if json_candidates:
        json_candidates.sort(key=lambda x: len(x[1]), reverse=True)
        for start_pos, candidate in json_candidates:
            try:
                parsed = json.loads(candidate)
                # If the JSON doesn't start at position 0, it might be incomplete
                # Check if it looks like a complete top-level object
                if start_pos == 0 or len(candidate) > 50:  # Substantial JSON
                    return candidate
                # Otherwise, it might be a nested object, continue to reconstruction
            except json.JSONDecodeError:
                continue
    
    # Fallback: try simple regex
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if json_match:
        matched = json_match.group(0)
        # Only use this if it's a substantial JSON (not just {} or a tiny fragment)
        # and it starts at the beginning of the text
        if len(matched) > 10 and text.strip().startswith('{'):
            return matched
    
    # Last resort: return text if it starts with {
    if text.startswith('{'):
        return text
    
    # Try to reconstruct incomplete JSON that starts with a value instead of {
    # Common patterns:
    # 1. "value", "key": "value"} - missing opening {
    # 2. e": "value", ...} - missing {"bot_respons
    # 3. ": "value", ...} - missing {"bot_response
    if text.endswith('}') and ':' in text:
        # Check if it looks like a partial JSON object (has key-value pairs)
        if ':' in text and '"' in text:
            # Handle case where it starts with ": (missing key and opening)
            if text.strip().startswith('":'):
                # Pattern: ": "value", "key": "value"}
                # Try common field names
                for field in ["bot_response", "response", "message", "text", "content"]:
                    reconstructed = f'{{"{field}": {text}'
                    try:
                        parsed = json.loads(reconstructed)
                        return reconstructed
                    except json.JSONDecodeError:
                        continue
            # Handle case where it starts with e": (missing "bot_respons)
            elif text.strip().startswith('e":'):
                # Pattern: e": "value", "key": "value"}
                # Remove the "e": part and add the full field name
                text_without_prefix = text[3:].strip()  # Remove 'e":'
                for field in ["bot_response", "response"]:
                    if field.endswith('e'):  # bot_response ends with 'e'
                        reconstructed = f'{{"{field}": {text_without_prefix}'
                        try:
                            parsed = json.loads(reconstructed)
                            return reconstructed
                        except json.JSONDecodeError:
                            continue
            # Handle case where it starts with a quoted value (like "hi", "key": "value"})
            elif text.strip().startswith('"') and ',' in text:
                # This might be: "value", "key": "value"}
                # Try to reconstruct: {"bot_response": "value", "key": "value"}
                first_comma = text.find(',')
                if first_comma > 0:
                    # Try common field names
                    for field in ["bot_response", "response", "message", "text"]:
                        reconstructed = f'{{"{field}": {text}'
                        try:
                            parsed = json.loads(reconstructed)
                            return reconstructed
                        except json.JSONDecodeError:
                            continue
            else:
                # Try simple wrapping
                reconstructed = '{' + text
                try:
                    json.loads(reconstructed)
                    return reconstructed
                except json.JSONDecodeError:
                    pass
    
    return ""


def normalize_extracted_data(extracted_data: dict) -> dict:
    """
    Normalize and validate extracted data to match expected enum values.
    
    This function enforces strict enum values for fields like payment_mode, 
    payment_reason, payee, etc.
    """
    if not isinstance(extracted_data, dict):
        return extracted_data
    
    normalized = extracted_data.copy()
    
    # Normalize payment_mode
    if 'payment_mode' in normalized and normalized['payment_mode']:
        mode = str(normalized['payment_mode']).lower()
        
        # Map variations to standard values
        if any(x in mode for x in ['upi', 'neft', 'rtgs', 'internet', 'online', 'net banking', 'netbanking']):
            if 'field' in mode or 'executive' in mode or 'agent' in mode:
                normalized['payment_mode'] = 'online_field_executive'
            else:
                normalized['payment_mode'] = 'online_lan'
        elif any(x in mode for x in ['cash', 'नकद', 'कैश']):
            normalized['payment_mode'] = 'cash'
        elif any(x in mode for x in ['branch', 'शाखा', 'ब्रांच']):
            normalized['payment_mode'] = 'branch'
        elif any(x in mode for x in ['outlet', 'आउटलेट']):
            normalized['payment_mode'] = 'outlet'
        elif any(x in mode for x in ['nach', 'ecs', 'auto', 'mandate']):
            normalized['payment_mode'] = 'nach'
        # If none match, keep original but log warning
        elif mode not in ['online_lan', 'online_field_executive', 'cash', 'branch', 'outlet', 'nach']:
            logger.warning(f"Unmapped payment_mode '{mode}', defaulting to online_lan")
            normalized['payment_mode'] = 'online_lan'
    
    # Normalize payment_reason
    if 'payment_reason' in normalized and normalized['payment_reason']:
        reason = str(normalized['payment_reason']).lower()
        
        # Check for combined emi + charges
        if ('emi' in reason and ('charge' in reason or 'fee' in reason or 'शुल्क' in reason)):
            normalized['payment_reason'] = 'emi_charges'
        elif 'emi' in reason:
            normalized['payment_reason'] = 'emi'
        elif any(x in reason for x in ['settle', 'settlement', 'निपटान']):
            normalized['payment_reason'] = 'settlement'
        elif any(x in reason for x in ['foreclos', 'पूर्व बंद', 'फोरक्लोज़']):
            normalized['payment_reason'] = 'foreclosure'
        elif any(x in reason for x in ['charge', 'fee', 'शुल्क']):
            normalized['payment_reason'] = 'charges'
        elif any(x in reason for x in ['cancel', 'रद्द']):
            normalized['payment_reason'] = 'loan_cancellation'
        elif any(x in reason for x in ['advance', 'अग्रिम']):
            normalized['payment_reason'] = 'advance_emi'
        elif reason not in ['emi', 'emi_charges', 'settlement', 'foreclosure', 'charges', 'loan_cancellation', 'advance_emi']:
            logger.warning(f"Unmapped payment_reason '{reason}', defaulting to emi")
            normalized['payment_reason'] = 'emi'
    
    # Normalize payee
    if 'payee' in normalized and normalized['payee']:
        payee = str(normalized['payee']).lower()
        
        if any(x in payee for x in ['self', 'खुद', 'मैं', 'स्वयं']):
            normalized['payee'] = 'self'
        elif any(x in payee for x in ['relative', 'family', 'परिवार', 'रिश्तेदार', 'भाई', 'बहन', 'पत्नी', 'पति', 'माता', 'पिता']):
            normalized['payee'] = 'relative'
        elif any(x in payee for x in ['friend', 'दोस्त', 'मित्र']):
            normalized['payee'] = 'friend'
        elif any(x in payee for x in ['third', 'other', 'अन्य', 'कोई और']):
            normalized['payee'] = 'third_party'
        elif payee not in ['self', 'relative', 'friend', 'third_party']:
            logger.warning(f"Unmapped payee '{payee}', defaulting to self")
            normalized['payee'] = 'self'
    
    # Normalize identity_confirmed
    if 'identity_confirmed' in normalized and normalized['identity_confirmed']:
        identity = str(normalized['identity_confirmed']).upper()
        if identity not in ['YES', 'NO', 'NOT_AVAILABLE', 'SENSITIVE_SITUATION']:
            # Try to map variations
            if any(x in identity.lower() for x in ['yes', 'हाँ', 'हा', 'जी']):
                normalized['identity_confirmed'] = 'YES'
            elif any(x in identity.lower() for x in ['no', 'नहीं', 'ना']):
                normalized['identity_confirmed'] = 'NO'
            elif any(x in identity.lower() for x in ['not available', 'unavailable', 'उपलब्ध नहीं']):
                normalized['identity_confirmed'] = 'NOT_AVAILABLE'
    
    # Normalize loan_taken and last_month_payment
    for field in ['loan_taken', 'last_month_payment']:
        if field in normalized and normalized[field]:
            value = str(normalized[field]).upper()
            if value not in ['YES', 'NO', 'DONT_KNOW']:
                if any(x in value.lower() for x in ['yes', 'हाँ', 'हा', 'ले लिया', 'किया']):
                    normalized[field] = 'YES'
                elif any(x in value.lower() for x in ['no', 'नहीं', 'ना']):
                    normalized[field] = 'NO'
                elif field == 'last_month_payment' and any(x in value.lower() for x in ['dont know', 'पता नहीं', 'याद नहीं']):
                    normalized[field] = 'DONT_KNOW'
    
    return normalized


def validate_and_fix_response(response_dict: dict, raw_text: str = "") -> dict:
    """
    Validate that response has all required fields and fix common issues.
    
    Required fields:
    - bot_response: str
    - extracted_data: dict
    - next_action: str
    - call_end_reason: str or null
    
    Returns a properly structured dict.
    """
    # Check if response already has all required fields
    has_bot_response = 'bot_response' in response_dict
    has_extracted_data = 'extracted_data' in response_dict
    has_next_action = 'next_action' in response_dict
    has_call_end_reason = 'call_end_reason' in response_dict
    
    # If all fields present, normalize extracted_data and return
    if has_bot_response and has_extracted_data and has_next_action and has_call_end_reason:
        response_dict['extracted_data'] = normalize_extracted_data(response_dict.get('extracted_data', {}))
        return response_dict
    """
    Validate that response has all required fields and fix common issues.
    
    Required fields:
    - bot_response: str
    - extracted_data: dict
    - next_action: str
    - call_end_reason: str or null
    
    Returns a properly structured dict.
    """
    # Check if response already has all required fields
    has_bot_response = 'bot_response' in response_dict
    has_extracted_data = 'extracted_data' in response_dict
    has_next_action = 'next_action' in response_dict
    has_call_end_reason = 'call_end_reason' in response_dict
    
    # If all fields present, normalize extracted_data and return
    if has_bot_response and has_extracted_data and has_next_action and has_call_end_reason:
        response_dict['extracted_data'] = normalize_extracted_data(response_dict.get('extracted_data', {}))
        return response_dict
    
    logger.warning(f"Response missing required fields. Has bot_response: {has_bot_response}, extracted_data: {has_extracted_data}")
    
    # Case 1: Response has ONLY data fields (no bot_response or structure)
    # This means the model returned something like: {"payment_date": "...", "payment_amount": "..."}
    # We need to restructure this
    
    data_fields = {}
    non_structure_keys = []
    
    for key in response_dict:
        if key not in ['bot_response', 'extracted_data', 'next_action', 'call_end_reason']:
            non_structure_keys.append(key)
            data_fields[key] = response_dict[key]
    
    # If we have data fields at root level, restructure the response
    if data_fields and not has_bot_response:
        logger.info(f"Restructuring response - found {len(data_fields)} data fields at root level")
        
        # Create a contextual bot response based on extracted data
        bot_response = generate_contextual_response(data_fields)
        
        return {
            'bot_response': bot_response,
            'extracted_data': normalize_extracted_data(data_fields),
            'next_action': response_dict.get('next_action', 'continue'),
            'call_end_reason': response_dict.get('call_end_reason', None)
        }
    
    # Case 2: Has bot_response but missing other fields
    if has_bot_response:
        return {
            'bot_response': response_dict.get('bot_response'),
            'extracted_data': normalize_extracted_data(response_dict.get('extracted_data', {})),
            'next_action': response_dict.get('next_action', 'continue'),
            'call_end_reason': response_dict.get('call_end_reason', None)
        }
    
    # Case 3: Completely malformed - return default structure
    logger.warning("Response completely malformed, returning default structure")
    return {
        'bot_response': response_dict.get('bot_response', 'ठीक है'),
        'extracted_data': response_dict.get('extracted_data', response_dict if isinstance(response_dict, dict) else {}),
        'next_action': 'continue',
        'call_end_reason': None
    }


def generate_contextual_response(data_fields: dict) -> str:
    """
    Generate a contextual Hindi bot response based on extracted data fields.
    
    This function creates natural, specific acknowledgments instead of generic responses.
    """
    # Payment information acknowledgment
    if 'payment_date' in data_fields or 'payment_amount' in data_fields or 'payment_mode' in data_fields:
        parts = []
        
        # Build acknowledgment based on available info
        if 'payment_amount' in data_fields:
            parts.append(f"{data_fields['payment_amount']} रुपये")
        
        if 'payment_date' in data_fields:
            # Convert date format if needed
            date_str = data_fields['payment_date']
            if '/' in date_str:
                day = date_str.split('/')[0]
                parts.append(f"{day} तारीख को")
            else:
                parts.append(f"{date_str} को")
        
        if 'payment_mode' in data_fields:
            mode = data_fields['payment_mode']
            mode_hindi = {
                'branch': 'ब्रांच में',
                'online_lan': 'ऑनलाइन',
                'cheque': 'चेक से',
                'cash': 'कैश में',
                'upi': 'UPI से'
            }.get(mode, mode)
            parts.append(mode_hindi)
        
        if 'payment_reason' in data_fields:
            reason = data_fields['payment_reason']
            reason_hindi = {
                'emi': 'EMI के लिए',
                'full_payment': 'पूरा भुगतान',
                'part_payment': 'आंशिक भुगतान'
            }.get(reason, reason)
            parts.append(reason_hindi)
        
        if parts:
            response = f"जी समझ गई, आपने {' '.join(parts)} दिए थे"
            return response
        else:
            return "जी, मैं आपकी पेमेंट की जानकारी नोट कर रही हूँ"
    
    # Identity confirmation
    if 'identity_confirmed' in data_fields:
        if data_fields['identity_confirmed'] == 'YES':
            if 'name' in data_fields:
                return f"धन्यवाद {data_fields['name']} जी, मैं आपकी पहचान की पुष्टि कर चुकी हूँ"
            return "धन्यवाद, मैं आपकी पहचान की पुष्टि कर चुकी हूँ"
        else:
            return "ठीक है, मैं समझ गई"
    
    # Loan confirmation
    if 'loan_taken' in data_fields:
        if data_fields['loan_taken'] == 'YES':
            return "जी, मुझे पता है आपने लोन लिया है"
        else:
            return "ठीक है, समझ गई"
    
    # Last month payment
    if 'last_month_payment' in data_fields:
        if data_fields['last_month_payment'] == 'YES':
            return "जी अच्छा, आपने पिछले महीने पेमेंट कर दिया था"
        else:
            return "ठीक है, मैं समझ गई"
    
    # Payee information
    if 'payee' in data_fields:
        if data_fields['payee'] == 'self':
            return "ठीक है, आपने खुद पेमेंट किया था"
        else:
            return f"समझ गई, {data_fields['payee']} ने पेमेंट किया था"
    
    # Generic fallback with data count
    field_count = len(data_fields)
    if field_count > 0:
        return "जी, मैं आपकी जानकारी नोट कर रही हूँ"
    
    return "ठीक है"


def call_mistral(prompt: str) -> dict:
    """Main function to call Mistral model - compatible with call_gemini interface"""
    overall_start = time.time()
    try:
        # Add date handling instructions to the prompt
        date_instruction = """
    IMPORTANT DATE RULES:
    - Current year is 2026
    - When processing dates, ALWAYS use 2026 as the year unless explicitly told otherwise
    - NEVER use years like 2025, 2024, 2023, or any year before 2026
    """
        
        # Enhance prompt with VERY strict JSON requirement
        enhanced_prompt = date_instruction + "\n\n" + prompt + """

    ═══════════════════════════════════════════════════════════════════════════
    🔴 MANDATORY JSON OUTPUT STRUCTURE - NO EXCEPTIONS
    ═══════════════════════════════════════════════════════════════════════════

    YOU MUST OUTPUT EXACTLY THIS STRUCTURE WITH ALL 4 FIELDS:

    {
    "bot_response": "your natural Hindi response here",
    "extracted_data": {
        // Put extracted customer data here, or leave empty: {}
    },
    "next_action": "continue",  // or "summary" or "end_call"
    "call_end_reason": null     // or reason string if ending call
    }

    ═══════════════════════════════════════════════════════════════════════════
    ⚠️ CRITICAL RULES - VIOLATION CAUSES SYSTEM ERROR:
    ═══════════════════════════════════════════════════════════════════════════

    1. FIRST CHARACTER must be: {
    2. LAST CHARACTER must be: }
    3. ALL 4 fields REQUIRED: bot_response, extracted_data, next_action, call_end_reason
    4. NO text before or after the JSON
    5. NO markdown (no ```json)
    6. Put extracted data INSIDE "extracted_data", NOT at root level

    ═══════════════════════════════════════════════════════════════════════════
    ✅ CORRECT EXAMPLES:
    ═══════════════════════════════════════════════════════════════════════════

    Example 1 (with extracted data):
    {"bot_response": "धन्यवाद, राज जी", "extracted_data": {"payment_date": "20/01/2026", "payment_amount": "5000"}, "next_action": "continue", "call_end_reason": null}

    Example 2 (no data extracted):
    {"bot_response": "नमस्ते", "extracted_data": {}, "next_action": "continue", "call_end_reason": null}

    Example 3 (ending call):
    {"bot_response": "धन्यवाद, अलविदा", "extracted_data": {}, "next_action": "end_call", "call_end_reason": "customer_busy"}

    ═══════════════════════════════════════════════════════════════════════════
    ❌ WRONG - DO NOT DO THIS:
    ═══════════════════════════════════════════════════════════════════════════

    WRONG 1 (missing fields):
    {"payment_date": "20/01/2026", "payment_amount": "5000"}

    WRONG 2 (data at root level):
    {"bot_response": "hi", "payment_date": "20/01/2026"}

    WRONG 3 (has text before):
    Here is the JSON: {"bot_response": "hi"}

    ═══════════════════════════════════════════════════════════════════════════

    NOW RESPOND WITH ONLY THE JSON (starting with { immediately):
    """
        
        # Call Mistral
        raw_response = _chat_completion(enhanced_prompt, temperature=0.1, require_json=True)
        
        if not raw_response:
            logger.warning("Empty response from Mistral")
            return {"value": "UNCLEAR", "is_clear": False}
        
        # Extract JSON from response
        json_text = extract_json_from_text(raw_response)
        
        if not json_text:
            logger.warning(f"No JSON found in response. First 200 chars: {raw_response[:200]}")
            return {"value": "UNCLEAR", "is_clear": False}
        
        # Parse JSON with better error handling
        try:
            result = json.loads(json_text)
            
            # 🔥 STEP 2: VALIDATE AND FIX RESPONSE STRUCTURE
            result = validate_and_fix_response(result, raw_response)
            
            total_elapsed = time.time() - overall_start
            logger.info(f"⏱️  Total call_mistral latency: {total_elapsed:.2f}s")
            return result
        except json.JSONDecodeError as json_err:
            # Try to fix common JSON issues
            json_text = re.sub(r',\s*}', '}', json_text)
            json_text = re.sub(r',\s*]', ']', json_text)
            try:
                result = json.loads(json_text)
                
                # 🔥 STEP 2: VALIDATE AND FIX RESPONSE STRUCTURE
                result = validate_and_fix_response(result, raw_response)
                
                total_elapsed = time.time() - overall_start
                logger.info(f"⏱️  Total call_mistral latency: {total_elapsed:.2f}s")
                return result
            except json.JSONDecodeError:
                logger.error(f"JSON Decode Error: {json_err}")
                logger.error(f"Extracted JSON text (first 500 chars): {json_text[:500]}")
                return {"value": "UNCLEAR", "is_clear": False}
        
    except Exception as e:
        logger.error(f"Error calling Mistral: {e}")
        import traceback
        traceback.print_exc()
        return {"value": "UNCLEAR", "is_clear": False}


class _ModelCompat:
    """Compatibility wrapper for model.generate_content used by summary_service"""
    
    def generate_content(self, prompt: str, generation_config: Optional[Dict[str, Any]] = None) -> _LLMResponse:
        temperature = 0.1
        if generation_config and isinstance(generation_config, dict):
            temperature = float(generation_config.get("temperature", temperature))
        
        text = _chat_completion(prompt, temperature=temperature, require_json=False)
        return _LLMResponse(text=text)


# Exported symbols
model = _ModelCompat()

# Alias for compatibility
call_gemini = call_mistral

