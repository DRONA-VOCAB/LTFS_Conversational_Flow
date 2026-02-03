from app.config.settings import OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL
from langchain_openai import ChatOpenAI
import json
import re
import time

# Initialize ChatOpenAI client
llm = ChatOpenAI(
    model_name=OPENAI_MODEL,
    openai_api_key=OPENAI_API_KEY,
    openai_api_base=OPENAI_BASE_URL,
    temperature=0.7,
    streaming=True,
)

# Optional: context tools (if available)
try:
    from .context_tools import get_tool_declarations, execute_context_tool
    CONTEXT_TOOLS_AVAILABLE = True
    print("[OpenAI] Context tools enabled. get_transcript_examples, get_session_summary will be used.")
except Exception as _e:
    CONTEXT_TOOLS_AVAILABLE = False
    print(
        "[OpenAI] Warning: context_tools not available (%s: %s). Context tools disabled."
        % (type(_e).__name__, _e)
    )


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
    """
    Call OpenAI model using LangChain ChatOpenAI.
    Maintains compatibility with existing Gemini function signature.
    """
    start_time = time.time()
    try:
        # Add system-level instructions for date handling and JSON output
        system_instruction = """
SYSTEM INSTRUCTIONS:
- Current year is 2026
- When processing dates, ALWAYS use 2026 as the year unless explicitly told otherwise
- NEVER use years like 2025, 2024, or any year before 2026
- Return ONLY valid JSON - no markdown, no explanations, no text outside JSON
"""
        
        enhanced_prompt = system_instruction + "\n\n" + prompt + "\n\nIMPORTANT: Return ONLY the JSON object. Do not include any text before or after the JSON. Start your response with { and end with }."
        
        # Call the OpenAI model
        response = llm.invoke(enhanced_prompt)
        
        # Calculate latency
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        
        print(f"[OpenAI] Response received - Latency: {latency_ms:.2f}ms")
        
        if not response or not response.content:
            print("Warning: Empty response from OpenAI")
            return {"value": "UNCLEAR", "is_clear": False}

        response_text = response.content
        
        # Extract JSON from response
        json_text = extract_json_from_text(response_text)

        if not json_text:
            print(f"Warning: No JSON found in response: {response_text}")
            return {"value": "UNCLEAR", "is_clear": False}

        # Parse JSON
        result = json.loads(json_text)

        # Add latency tracking to the result for observability
        if isinstance(result, dict):
            result["_latency_ms"] = round(latency_ms, 2)
            result["_model"] = OPENAI_MODEL
        
        return result
        
    except json.JSONDecodeError as e:
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        print(f"JSON Decode Error: {e}")
        print(f"Response text: {response.content if response else 'No response'}")
        print(f"[OpenAI] Error after {latency_ms:.2f}ms")
        return {"value": "UNCLEAR", "is_clear": False}
    except Exception as e:
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        print(f"Error calling OpenAI: {e}")
        print(f"[OpenAI] Error after {latency_ms:.2f}ms")
        return {"value": "UNCLEAR", "is_clear": False}


def call_gemini_with_tools(
    prompt: str,
    session: dict,
    user_input: str,
    conversation_stage: str,
) -> dict:
    """
    Call OpenAI with context-catching tools. The model can call
    get_transcript_examples and get_session_summary; we execute them and
    pass results back until the model returns a final JSON response.
    Falls back to call_gemini if context tools are unavailable.
    """
    start_time = time.time()
    
    if not CONTEXT_TOOLS_AVAILABLE:
        print("Warning: context_tools not available, using non-tool call_gemini")
        return call_gemini(prompt)

    # For now, fall back to regular call since tool integration with LangChain
    # would require more complex setup. This can be enhanced later if needed.
    print("Info: Using regular OpenAI call (tool integration not yet implemented)")
    result = call_gemini(prompt)
    
    # Add additional latency tracking for tools call
    end_time = time.time()
    latency_ms = (end_time - start_time) * 1000
    
    if isinstance(result, dict):
        result["_tools_latency_ms"] = round(latency_ms, 2)
    
    return result
