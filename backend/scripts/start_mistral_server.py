"""
Mistral-7B-Instruct-v0.3 Inference Server

Starts a FastAPI server on port 5001 that serves the Mistral model
with an OpenAI-compatible API endpoint.

Usage:
    python backend/scripts/start_mistral_server.py

Environment Variables:
    MISTRAL_MODEL_PATH: Path to model directory (default: ~/mistral_models/7B-Instruct-v0.3)
    MISTRAL_PORT: Port to serve on (default: 5001)
    MISTRAL_DEVICE: Device to use (default: cuda if available, else cpu)
    MISTRAL_HOST: Host to bind to (default: 0.0.0.0)
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
MISTRAL_MODEL_PATH = os.getenv(
    "MISTRAL_MODEL_PATH",
    str(Path.home().joinpath("mistral_models", "7B-Instruct-v0.3"))
)
MISTRAL_PORT = int(os.getenv("MISTRAL_PORT", "5001"))
MISTRAL_HOST = os.getenv("MISTRAL_HOST", "0.0.0.0")  # 0.0.0.0 allows access from network (192.168.30.121)
MISTRAL_DEVICE = os.getenv("MISTRAL_DEVICE")

# Global model and tokenizer
_model = None
_tokenizer = None

# Try to import transformers
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    TRANSFORMERS_AVAILABLE = True
    if not MISTRAL_DEVICE:
        MISTRAL_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"✅ Transformers available. CUDA available: {torch.cuda.is_available()}")
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.error("❌ Transformers not available. Install with: pip install transformers torch")
    sys.exit(1)

# FastAPI app
app = FastAPI(
    title="Mistral-7B-Instruct-v0.3 API Server",
    version="1.0.0",
    description="OpenAI-compatible API server for Mistral-7B-Instruct-v0.3"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_model():
    """Load the Mistral model with 4-bit quantization for faster inference"""
    global _model, _tokenizer
    
    if _model is not None and _tokenizer is not None:
        logger.info("Model already loaded")
        return _model, _tokenizer
    
    import torch
    from transformers import BitsAndBytesConfig
    
    model_path = Path(MISTRAL_MODEL_PATH)
    model_id = "mistralai/Mistral-7B-Instruct-v0.3"
    
    logger.info(f"🔄 Loading Mistral model with 4-bit quantization...")
    logger.info(f"📱 Device: {MISTRAL_DEVICE}")
    
    # Configure 4-bit quantization for faster inference and lower memory
    quantization_config = None
    use_quantization = MISTRAL_DEVICE == "cuda" and torch.cuda.is_available()
    
    if use_quantization:
        logger.info("🚀 Using 4-bit quantization for faster inference")
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,  # Double quantization for better compression
            bnb_4bit_quant_type="nf4"  # Normal float 4-bit
        )
    
    # Check if local path has config.json (required for transformers)
    use_local = model_path.exists() and (model_path / "config.json").exists()
    
    if use_local:
        logger.info(f"Loading from local path: {model_path}")
        try:
            _tokenizer = AutoTokenizer.from_pretrained(str(model_path), trust_remote_code=True)
            if use_quantization:
                _model = AutoModelForCausalLM.from_pretrained(
                    str(model_path),
                    quantization_config=quantization_config,
                    device_map="auto",
                    trust_remote_code=True
                )
            else:
                _model = AutoModelForCausalLM.from_pretrained(
                    str(model_path),
                    torch_dtype=torch.float16 if MISTRAL_DEVICE == "cuda" else torch.float32,
                    device_map="auto" if MISTRAL_DEVICE == "cuda" else None,
                    trust_remote_code=True
                )
                if MISTRAL_DEVICE == "cpu":
                    _model = _model.to(MISTRAL_DEVICE)
        except Exception as e:
            logger.warning(f"Failed to load from local path: {e}")
            logger.info(f"Falling back to Hugging Face: {model_id}")
            use_local = False
    
    if not use_local:
        logger.info(f"Loading from Hugging Face: {model_id}")
        logger.info("This may take a few minutes on first run...")
        _tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        if use_quantization:
            _model = AutoModelForCausalLM.from_pretrained(
                model_id,
                quantization_config=quantization_config,
                device_map="auto",
                trust_remote_code=True
            )
        else:
            _model = AutoModelForCausalLM.from_pretrained(
                model_id,
                torch_dtype=torch.float16 if MISTRAL_DEVICE == "cuda" else torch.float32,
                device_map="auto" if MISTRAL_DEVICE == "cuda" else None,
                trust_remote_code=True
            )
            if MISTRAL_DEVICE == "cpu":
                _model = _model.to(MISTRAL_DEVICE)
    
    _model.eval()
    
    # Log memory usage
    if torch.cuda.is_available() and MISTRAL_DEVICE == "cuda":
        memory_allocated = torch.cuda.memory_allocated() / 1024**3
        memory_reserved = torch.cuda.memory_reserved() / 1024**3
        logger.info(f"📊 GPU Memory: {memory_allocated:.2f}GB allocated, {memory_reserved:.2f}GB reserved")
        if use_quantization:
            logger.info(f"⚡ 4-bit quantization enabled - expect 1.5-2x faster inference")
    
    logger.info(f"✅ Model loaded successfully on {MISTRAL_DEVICE}")
    return _model, _tokenizer


# Pydantic models for API
class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "mistral-7b-instruct"
    messages: List[Message]
    temperature: float = 0.1
    max_tokens: int = 2048
    top_p: float = 0.95


class Choice(BaseModel):
    index: int
    message: Message
    finish_reason: str


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Usage


@app.on_event("startup")
async def startup_event():
    """Load model on startup"""
    logger.info("🚀 Starting Mistral inference server...")
    try:
        load_model()
        logger.info(f"✅ Server ready on http://{MISTRAL_HOST}:{MISTRAL_PORT}")
    except Exception as e:
        logger.error(f"❌ Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        raise


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "model": "mistral-7b-instruct",
        "model_path": MISTRAL_MODEL_PATH,
        "device": MISTRAL_DEVICE,
        "model_loaded": _model is not None
    }


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy", "model_loaded": _model is not None}


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint"""
    import torch
    import time
    
    if _model is None or _tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        # Format messages for Mistral Instruct
        # Combine system and user messages
        formatted_prompt = ""
        for msg in request.messages:
            if msg.role == "system":
                formatted_prompt += f"{msg.content}\n\n"
            elif msg.role == "user":
                formatted_prompt += f"{msg.content}\n"
            elif msg.role == "assistant":
                formatted_prompt += f"{msg.content}\n"
        
        # Add Mistral Instruct format
        formatted_prompt = f"<s>[INST] {formatted_prompt.strip()} [/INST]"
        
        # Tokenize
        inputs = _tokenizer(formatted_prompt, return_tensors="pt")
        if MISTRAL_DEVICE == "cuda" and torch.cuda.is_available():
            inputs = inputs.to("cuda")
        else:
            inputs = inputs.to("cpu")
        
        # Generate
        start_time = time.time()
        with torch.no_grad():
            outputs = _model.generate(
                **inputs,
                max_new_tokens=request.max_tokens,
                temperature=request.temperature,
                do_sample=request.temperature > 0,
                top_p=request.top_p,
                pad_token_id=_tokenizer.eos_token_id,
            )
        
        # Decode
        generated_text = _tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Extract response (remove the prompt part)
        if "[/INST]" in generated_text:
            response_text = generated_text.split("[/INST]")[-1].strip()
        else:
            response_text = generated_text[len(formatted_prompt):].strip()
        
        generation_time = time.time() - start_time
        
        # Calculate token usage (approximate)
        prompt_tokens = len(_tokenizer.encode(formatted_prompt))
        completion_tokens = len(_tokenizer.encode(response_text))
        
        logger.info(f"Generated response in {generation_time:.2f}s ({completion_tokens} tokens)")
        
        # Return OpenAI-compatible response
        return ChatCompletionResponse(
            id=f"chatcmpl-{int(time.time())}",
            created=int(time.time()),
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=Message(role="assistant", content=response_text),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            )
        )
        
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def list_models():
    """List available models"""
    return {
        "object": "list",
        "data": [
            {
                "id": "mistral-7b-instruct",
                "object": "model",
                "created": 1699999999,
                "owned_by": "mistralai"
            }
        ]
    }


if __name__ == "__main__":
    logger.info(f"Starting Mistral server on {MISTRAL_HOST}:{MISTRAL_PORT}")
    logger.info(f"Model path: {MISTRAL_MODEL_PATH}")
    logger.info(f"Device: {MISTRAL_DEVICE}")
    
    uvicorn.run(
        app,
        host=MISTRAL_HOST,
        port=MISTRAL_PORT,
        log_level="info"
    )

