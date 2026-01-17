from ..config.settings import GEMINI_MODEL, GEMINI_API_KEY
import google.generativeai as genai
import json
import re


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
        
        response = model.generate_content(enhanced_prompt, generation_config=generation_config)
        
        if not response or not response.text:
            print("Warning: Empty response from Gemini")
            return {"value": "UNCLEAR", "is_clear": False}
        
        # Extract JSON from response
        json_text = extract_json_from_text(response.text)
        
        if not json_text:
            print(f"Warning: No JSON found in response: {response.text}")
            return {"value": "UNCLEAR", "is_clear": False}
        
        # Parse JSON
        result = json.loads(json_text)
        return result
        
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        print(f"Response text: {response.text if response else 'No response'}")
        return {"value": "UNCLEAR", "is_clear": False}
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        return {"value": "UNCLEAR", "is_clear": False}
