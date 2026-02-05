from config.settings import GEMINI_MODEL, GEMINI_API_KEY
import json
import re

# Use new SDK (google-genai) - required
try:
    from google import genai as genai_new
    from google.genai import types as genai_types
    GENAI_NEW_AVAILABLE = True
    print("[Gemini] Using google-genai SDK. Context tools enabled (get_transcript_examples, get_session_summary will be used).")
except Exception as _e:
    GENAI_NEW_AVAILABLE = False
    print(
        "[Gemini] ERROR: google-genai not available (%s: %s). "
        "Install with: pip install google-genai" % (type(_e).__name__, _e)
    )
    raise

# Create a client instance for simple text generation (backward compatibility)
_client = None
if GENAI_NEW_AVAILABLE:
    _client = genai_new.Client(api_key=GEMINI_API_KEY)


class SimpleModelWrapper:
    """Wrapper class to mimic the old google.generativeai.GenerativeModel API"""
    def __init__(self, model_name: str):
        self.model_name = model_name
    
    def generate_content(self, prompt: str, generation_config: dict = None):
        """Generate content using the new SDK, returning a response object with .text attribute"""
        if not GENAI_NEW_AVAILABLE or not _client:
            raise RuntimeError("google-genai SDK not available")
        
        config = genai_types.GenerateContentConfig(
            temperature=generation_config.get("temperature", 0.7) if generation_config else 0.7,
            top_p=generation_config.get("top_p", 0.95) if generation_config else 0.95,
        )
        
        user_part = genai_types.Part.from_text(text=prompt)
        contents = [genai_types.Content(role="user", parts=[user_part])]
        
        response = _client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=config,
        )
        
        # Return a response object that mimics the old API
        class ResponseWrapper:
            def __init__(self, response):
                self._response = response
                self.text = ""
                if response and response.candidates:
                    text_parts = []
                    for part in response.candidates[0].content.parts:
                        if getattr(part, "text", None):
                            text_parts.append(part.text)
                    self.text = "".join(text_parts).strip()
                
                # Store usage metadata if available
                self.usage_metadata = None
                try:
                    self.usage_metadata = getattr(response, "usage_metadata", None)
                except Exception:
                    pass
        
        return ResponseWrapper(response)


# Create a model instance for backward compatibility
model = SimpleModelWrapper(GEMINI_MODEL) if GENAI_NEW_AVAILABLE else None


def extract_json_from_text(text: str) -> str:
    """Extract JSON from text, handling markdown code blocks and preceding text"""
    if not text:
        return ""
    
    # Remove markdown code blocks if present
    text = text.strip()
    
    # Check if wrapped in ```json or ``` blocks
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        return json_match.group(1)
    
    # Find JSON object by finding matching braces (handles nested structures)
    # Start from the first { and find the matching }
    start_idx = text.find('{')
    if start_idx == -1:
        return text.strip()
    
    # Count braces to find the matching closing brace
    brace_count = 0
    in_string = False
    escape_next = False
    
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
                    return text[start_idx:i+1]
    
    # Fallback: try simple regex if brace matching fails
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        return json_match.group(0)
    
    return text.strip()


def call_gemini(prompt: str) -> dict:
    """Call Gemini using the new google-genai SDK (no tools)."""
    if not GENAI_NEW_AVAILABLE:
        print("ERROR: google-genai SDK not available")
        return {"value": "UNCLEAR", "is_clear": False}
    
    response = None
    try:
        # Add system-level instructions for date handling and JSON output
        system_instruction = """
SYSTEM INSTRUCTIONS:
- Current year is 2025
- When processing dates, ALWAYS use 2025 as the year unless explicitly told otherwise
- NEVER use years like 2024, 2023, or any year before 2025
- Return ONLY valid JSON - no markdown, no explanations, no text outside JSON
"""
        
        enhanced_prompt = system_instruction + "\n\n" + prompt + "\n\nIMPORTANT: Return ONLY the JSON object. Do not include any text before or after the JSON. Start your response with { and end with }."
        
        # Use new SDK API
        client = genai_new.Client(api_key=GEMINI_API_KEY)
        config = genai_types.GenerateContentConfig(
            temperature=0.1,  # Lower temperature for more consistent output
            top_p=0.8,
        )
        
        user_part = genai_types.Part.from_text(text=enhanced_prompt)
        contents = [genai_types.Content(role="user", parts=[user_part])]
        
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=config,
        )

        if not response or not response.candidates:
            print("Warning: Empty response from Gemini")
            return {"value": "UNCLEAR", "is_clear": False}

        # Extract text from response (new SDK structure)
        text_parts = []
        for part in response.candidates[0].content.parts:
            if getattr(part, "text", None):
                text_parts.append(part.text)
        
        response_text = "".join(text_parts).strip()
        
        if not response_text:
            print("Warning: Empty response text from Gemini")
            return {"value": "UNCLEAR", "is_clear": False}

        # Try to capture token usage if available
        input_tokens = output_tokens = total_tokens = None
        try:
            usage = getattr(response, "usage_metadata", None)
            if usage is not None:
                input_tokens = getattr(usage, "prompt_token_count", None)
                output_tokens = getattr(usage, "candidates_token_count", None)
                total_tokens = getattr(usage, "total_token_count", None)
                print(
                    f"[Gemini usage] input_tokens={input_tokens}, "
                    f"output_tokens={output_tokens}, total_tokens={total_tokens}"
                )
        except Exception as usage_err:
            # Usage metadata is best-effort; don't break on failure
            print(f"Warning: unable to read Gemini usage metadata: {usage_err}")

        # Extract JSON from response
        json_text = extract_json_from_text(response_text)

        if not json_text:
            print(f"Warning: No JSON found in response: {response_text}")
            return {"value": "UNCLEAR", "is_clear": False}

        # Parse JSON
        result = json.loads(json_text)

        # Attach token counts for observability (does not affect core schema)
        if isinstance(result, dict):
            if input_tokens is not None:
                result["_input_tokens"] = input_tokens
            if output_tokens is not None:
                result["_output_tokens"] = output_tokens
            if total_tokens is not None:
                result["_total_tokens"] = total_tokens

        return result
        
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        response_text = ""
        if response and response.candidates:
            for part in response.candidates[0].content.parts:
                if getattr(part, "text", None):
                    response_text += part.text
        print(f"Response text: {response_text if response_text else 'No response'}")
        return {"value": "UNCLEAR", "is_clear": False}
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        return {"value": "UNCLEAR", "is_clear": False}


def call_gemini_with_tools(
    prompt: str,
    session: dict,
    user_input: str,
    conversation_stage: str,
) -> dict:
    """
    Call Gemini with context-catching tools. The model can call
    get_transcript_examples and get_session_summary; we execute them and
    pass results back until the model returns a final JSON response.
    Falls back to call_gemini if the new SDK or tools are unavailable.
    """
    if not GENAI_NEW_AVAILABLE:
        print("Warning: google-genai not available, using non-tool call_gemini")
        return call_gemini(prompt)

    try:
        from .context_tools import get_tool_declarations, execute_context_tool
    except Exception as e:
        print(f"Warning: context_tools unavailable ({e}), using non-tool call_gemini")
        return call_gemini(prompt)

    system_instruction = """
SYSTEM INSTRUCTIONS:
- Current year is 2025
- When processing dates, ALWAYS use 2025 as the year unless explicitly told otherwise
- Return ONLY valid JSON - no markdown, no explanations, no text outside JSON
- You MAY call get_transcript_examples or get_session_summary to get more context before responding.
- After using tool results, respond with the final JSON (bot_response, extracted_data, next_action, etc.).
"""
    enhanced_prompt = (
        system_instruction
        + "\n\n"
        + prompt
        + "\n\nIMPORTANT: Return ONLY the JSON object. Start your response with { and end with }."
    )

    try:
        client = genai_new.Client(api_key=GEMINI_API_KEY)
        tools_list = genai_types.Tool(function_declarations=get_tool_declarations())
        config = genai_types.GenerateContentConfig(
            tools=[tools_list],
            temperature=0.1,
        )
        # Build initial user content (google-genai uses keyword-only: Part.from_text(text=...))
        user_part = genai_types.Part.from_text(text=enhanced_prompt)
        contents = [genai_types.Content(role="user", parts=[user_part])]
        max_tool_rounds = 5
        final_text = None
        input_tokens = output_tokens = total_tokens = None

        for _ in range(max_tool_rounds):
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )
            if not response or not response.candidates:
                break
            try:
                usage = getattr(response, "usage_metadata", None)
                if usage:
                    input_tokens = getattr(usage, "prompt_token_count", None)
                    output_tokens = getattr(usage, "candidates_token_count", None)
                    total_tokens = getattr(usage, "total_token_count", None)
            except Exception:
                pass

            parts = response.candidates[0].content.parts
            function_calls = []
            text_parts = []
            for part in parts:
                fc = getattr(part, "function_call", None)
                if fc:
                    function_calls.append((getattr(fc, "name", ""), getattr(fc, "args", None) or {}))
                if getattr(part, "text", None):
                    text_parts.append(part.text)

            if text_parts and not function_calls:
                final_text = "".join(text_parts).strip()
                break

            if not function_calls:
                break

            contents.append(response.candidates[0].content)
            for name, args in function_calls:
                result = execute_context_tool(
                    name, args or {}, session, user_input, conversation_stage
                )
                part = genai_types.Part.from_function_response(name=name, response=result)
                contents.append(genai_types.Content(role="user", parts=[part]))

        if not final_text:
            print("Warning: No final text from tool-enabled Gemini, falling back to call_gemini")
            return call_gemini(prompt)
    except Exception as e:
        print(f"Warning: call_gemini_with_tools failed ({e}), falling back to call_gemini")
        return call_gemini(prompt)

    json_text = extract_json_from_text(final_text)
    if not json_text:
        print(f"Warning: No JSON in tool response: {final_text[:500]}")
        return call_gemini(prompt)
    result = json.loads(json_text)
    if isinstance(result, dict):
        if input_tokens is not None:
            result["_input_tokens"] = input_tokens
        if output_tokens is not None:
            result["_output_tokens"] = output_tokens
        if total_tokens is not None:
            result["_total_tokens"] = total_tokens
    return result
