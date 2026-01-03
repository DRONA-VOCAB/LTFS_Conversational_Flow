import google.generativeai as genai
from config import settings
from typing import Dict, Optional
import json
from services.question_prompts import get_question_prompt

genai.configure(api_key=settings.gemini_api_key)


async def analyze_response(
    question_number: float,
    question_text: str,
    customer_response: str,
    context: str = "",
    conversation_history: list = None,
) -> Dict:
    """Analyze customer response using Gemini AI with question-specific prompts"""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")

        # Get question-specific prompt
        full_prompt = get_question_prompt(
            question_number=question_number,
            question_text=question_text,
            customer_response=customer_response,
            conversation_history=conversation_history,
        )

        print(f"\n{'='*80}")
        print(f"🤖 GEMINI PROMPT (Question {question_number}):")
        print(f"{full_prompt}")
        print(f"{'='*80}\n")

        response = model.generate_content(full_prompt)

        # Extract JSON from response
        response_text = response.text.strip()

        # Try to find JSON in the response
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1

        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            result = json.loads(json_str)

            # Ensure next_question is present
            if "next_question" not in result:
                # Default next question logic
                if (
                    result.get("should_proceed")
                    and result.get("status") == "valid_answer"
                ):
                    result["next_question"] = (
                        str(question_number + 1)
                        if isinstance(question_number, int)
                        else str(float(question_number) + 0.1)
                    )
                else:
                    result["next_question"] = str(question_number)

            return result
        else:
            # Fallback if JSON parsing fails
            print(f"⚠️ Could not parse JSON from Gemini response: {response_text}")
            return {
                "status": "clarification_needed",
                "extracted_answer": "",
                "confidence": 0.0,
                "should_proceed": False,
                "next_question": str(question_number),
                "bot_response": "माफ़ करें, क्या आप दोबारा बता सकते हैं?",
            }

    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ GEMINI ERROR:")
        print(f"   Error: {str(e)}")
        print(f"{'='*80}\n")
        import traceback

        traceback.print_exc()
        return {
            "status": "clarification_needed",
            "extracted_answer": "",
            "confidence": 0.0,
            "should_proceed": False,
            "next_question": str(question_number),
            "bot_response": "माफ़ करें, क्या आप दोबारा बता सकते हैं?",
        }
