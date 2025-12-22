"""LLM service using Gemini API for natural language understanding."""
import httpx
from typing import Optional, Dict, Any
import time
from app.config import settings


class LLMService:
    """Service for LLM interactions using Gemini API."""
    
    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def generate_response(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Generate response using Gemini API.
        Only used when mapping functions fail to understand the response.
        
        Args:
            prompt: The prompt/question
            context: Additional context
        
        Returns:
            Generated text or None if error
        """
        if not self.api_key:
            print("[LLM] API key not configured")
            return None
        
        start_time = time.perf_counter()
        try:
            url = f"{self.base_url}?key={self.api_key}"
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }]
            }
            
            if context:
                # Add context to prompt
                context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
                payload["contents"][0]["parts"][0]["text"] = f"{prompt}\n\nContext:\n{context_str}"
            
            response = await self.client.post(url, json=payload)
            latency = time.perf_counter() - start_time
            
            # Handle rate limiting (429) with retry
            if response.status_code == 429:
                error_data = response.json() if response.text else {}
                retry_after = 60  # Default 60 seconds
                
                # Try to extract retry delay from error response
                if "details" in error_data.get("error", {}):
                    for detail in error_data["error"]["details"]:
                        if detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
                            retry_after = int(float(detail.get("retryDelay", "60s").replace("s", "")))
                
                print(f"[LLM] Rate limit exceeded. Retry after {retry_after} seconds (latency: {latency:.3f}s)")
                return None  # Return None to trigger fallback response
            
            if response.status_code == 200:
                result = response.json()
                # Extract text from Gemini response
                if "candidates" in result and len(result["candidates"]) > 0:
                    candidate = result["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        parts = candidate["content"]["parts"]
                        if parts and "text" in parts[0]:
                            text = parts[0]["text"].strip()
                            print(f"[LLM] generate_response latency: {latency:.3f}s, prompt length: {len(prompt)} chars, response length: {len(text)} chars")
                            return text
                
                print(f"[LLM] generate_response latency: {latency:.3f}s, but no text extracted")
                return None
            else:
                print(f"[LLM] Error: {response.status_code} - {response.text} (latency: {latency:.3f}s)")
                return None
                
        except Exception as e:
            latency = time.perf_counter() - start_time
            print(f"[LLM] Exception: {str(e)} (latency: {latency:.3f}s)")
            return None
    
    async def classify_intent(
        self,
        text: str,
        options: list,
        question_type: str = "yes_no"
    ) -> Optional[str]:
        """
        Classify intent from text when mapping functions fail.
        This is a fallback to LLM when simple keyword matching doesn't work.
        
        Args:
            text: User input text
            options: List of possible options/values
            question_type: Type of question (yes_no, choice, etc.)
        
        Returns:
            Classified option or None
        """
        start_time = time.perf_counter()
        if question_type == "yes_no":
            prompt = f"""Given the following user response, determine if it means YES or NO.
User response: "{text}"

Respond with only "YES" or "NO" or "UNCLEAR"."""
        else:
            options_str = ", ".join(options)
            prompt = f"""Given the following user response, classify it into one of these options: {options_str}
User response: "{text}"

Respond with only one of the options or "UNCLEAR"."""
        
        result = await self.generate_response(prompt)
        total_latency = time.perf_counter() - start_time
        
        if result:
            result_upper = result.upper().strip()
            if question_type == "yes_no":
                if "YES" in result_upper:
                    print(f"[LLM] classify_intent latency: {total_latency:.3f}s, classified as: yes")
                    return "yes"
                elif "NO" in result_upper:
                    print(f"[LLM] classify_intent latency: {total_latency:.3f}s, classified as: no")
                    return "no"
            else:
                for option in options:
                    if option.upper() in result_upper:
                        print(f"[LLM] classify_intent latency: {total_latency:.3f}s, classified as: {option}")
                        return option
        
        print(f"[LLM] classify_intent latency: {total_latency:.3f}s, no classification found")
        return None
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

