import google.generativeai as genai
from config import settings
from typing import Dict, Optional
import json

genai.configure(api_key=settings.gemini_api_key)


def get_system_prompt(question_number: int, question_text: str, context: str = "") -> str:
    """Generate system prompt based on question number"""
    
    base_prompt = """You are a professional customer service representative for L&T Finance conducting a feedback call in Hindi. 
Your role is to analyze customer responses and determine:
1. If the customer answered the question properly (valid answer)
2. If the customer is speaking off-topic
3. If the customer is not interested
4. If the customer is busy/not available
5. If the customer needs clarification or repeat

Current Question: {question}

Previous Context: {context}

Analyze the customer's response and provide a JSON response with:
{{
    "status": "valid_answer" | "off_topic" | "not_interested" | "busy" | "clarification_needed" | "no_response",
    "extracted_answer": "the actual answer if status is valid_answer, otherwise empty string",
    "confidence": 0.0-1.0,
    "reason": "brief reason for the status",
    "should_proceed": true/false,
    "bot_response": "appropriate Hindi response to give to customer based on the status"
}}

Rules:
- If status is "valid_answer" and should_proceed is true, move to next question
- If status is "clarification_needed", repeat the question or ask for clarification
- If status is "off_topic", politely redirect to the question
- If status is "not_interested" or "busy", attempt graceful exit after 2-3 tries
- If status is "no_response" after multiple attempts, mark for graceful exit
- Always respond in polite, professional Hindi
"""
    
    return base_prompt.format(question=question_text, context=context)


async def analyze_response(
    question_number: int,
    question_text: str,
    customer_response: str,
    context: str = "",
    conversation_history: list = None
) -> Dict:
    """Analyze customer response using Gemini AI"""
    
    try:
        model = genai.GenerativeModel('gemini-pro')
        
        system_prompt = get_system_prompt(question_number, question_text, context)
        
        conversation_context = ""
        if conversation_history:
            # Handle both dict format and tuple format
            formatted_history = []
            for item in conversation_history[-3:]:
                if isinstance(item, dict):
                    q = item.get("question", "")
                    a = item.get("customer_response", "")
                else:
                    q, a = item
                formatted_history.append(f"Q: {q}\nA: {a}")
            conversation_context = "\n".join(formatted_history)
        
        full_prompt = f"""{system_prompt}

Conversation History:
{conversation_context}

Customer's Current Response: {customer_response}

Please analyze this response and provide the JSON analysis as specified above."""
        
        response = model.generate_content(full_prompt)
        
        # Extract JSON from response
        response_text = response.text.strip()
        
        # Try to find JSON in the response
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            result = json.loads(json_str)
            return result
        else:
            # Fallback if JSON parsing fails
            return {
                "status": "clarification_needed",
                "extracted_answer": "",
                "confidence": 0.0,
                "reason": "Could not parse response",
                "should_proceed": False,
                "bot_response": "माफ़ करें, क्या आप दोबारा बता सकते हैं?"
            }
            
    except Exception as e:
        print(f"Gemini Error: {str(e)}")
        return {
            "status": "clarification_needed",
            "extracted_answer": "",
            "confidence": 0.0,
            "reason": f"Error: {str(e)}",
            "should_proceed": False,
            "bot_response": "माफ़ करें, क्या आप दोबारा बता सकते हैं?"
        }

