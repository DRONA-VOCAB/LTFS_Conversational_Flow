from config.settings import GEMINI_MODEL, GEMINI_API_KEY
import google.generativeai as genai
import json
import re

# Optional: new SDK for tool calling (context catching)
try:
    from google import genai as genai_new
    from google.genai import types as genai_types
    GENAI_NEW_AVAILABLE = True
    print("[Gemini] Context tools enabled (google-genai SDK). get_transcript_examples, get_session_summary will be used.")
except Exception as _e:
    GENAI_NEW_AVAILABLE = False
    print(
        "[Gemini] Warning: google-genai not available (%s: %s). Context tools disabled. "
        "Install with: pip install google-genai" % (type(_e).__name__, _e)
    )

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(model_name=GEMINI_MODEL)


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
        
        # Use generation config to encourage structured output
        generation_config = {
            "temperature": 0.1,  # Lower temperature for more consistent output
            "top_p": 0.8,
        }
        
        response = model.generate_content(
            enhanced_prompt, generation_config=generation_config
        )

        if not response or not response.text:
            print("Warning: Empty response from Gemini")
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
        json_text = extract_json_from_text(response.text)

        if not json_text:
            print(f"Warning: No JSON found in response: {response.text}")
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
        print(f"Response text: {response.text if response else 'No response'}")
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
