from config.settings import GEMINI_MODEL, GEMINI_API_KEY
import google.generativeai as genai
import json
import re


genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(model_name=GEMINI_MODEL)


def extract_json_from_text(text: str) -> str:
    """Extract JSON from text, handling markdown code blocks"""
    if not text:
        return ""
    
    # Remove markdown code blocks if present
    text = text.strip()
    
    # Check if wrapped in ```json or ``` blocks
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        return json_match.group(1)
    
    # Check if it's just JSON wrapped in braces
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        return json_match.group(0)
    
    return text.strip()


def call_gemini(prompt: str) -> dict:
    try:
        response = model.generate_content(prompt)
        
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
