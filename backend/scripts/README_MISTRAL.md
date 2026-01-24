# Mistral-7B-Instruct-v0.3 Integration Guide

This guide explains how to set up and use Mistral-7B-Instruct-v0.3 with the LTFS Conversational Flow system.

## Quick Start

### 1. Download the Model

Run the download script:

```bash
cd backend
python scripts/download_mistral_model.py
```

This will download the model to `~/mistral_models/7B-Instruct-v0.3/`

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `huggingface_hub` - For downloading models
- `transformers` - For model inference
- `accelerate` - For efficient model loading
- `safetensors` - For safe tensor loading

### 3. Configure Environment

Add to your `.env` file:

```bash
# Select Mistral as LLM provider
LLM_PROVIDER=mistral

# Option 1: Direct Inference (loads model in memory)
MISTRAL_MODEL_PATH=~/mistral_models/7B-Instruct-v0.3
MISTRAL_DEVICE=cuda  # or "cpu" if no GPU
MISTRAL_USE_API=false

# Option 2: API-based Inference (if you have a separate inference server)
# MISTRAL_USE_API=true
# MISTRAL_API_BASE=http://localhost:8000
# MISTRAL_API_KEY=local
```

## Usage Modes

### Mode 1: Direct Inference (Recommended for Single Instance)

The model is loaded directly into memory. Best for:
- Single server instance
- Dedicated GPU server
- Lower latency requirements

**Pros:**
- No network overhead
- Lower latency
- Full control

**Cons:**
- Higher memory usage (~14GB for 7B model)
- Slower startup time
- One model per process

### Mode 2: API-based Inference

Use a separate inference server (e.g., vLLM, llama.cpp server). Best for:
- Multiple application instances
- Shared GPU resources
- Scalability

**Setup vLLM Server:**
```bash
# Install vLLM
pip install vllm

# Start server
vllm serve mistralai/Mistral-7B-Instruct-v0.3 \
  --host 0.0.0.0 \
  --port 8000 \
  --max-model-len 8192
```

**Pros:**
- Shared model across instances
- Better resource utilization
- Easier scaling

**Cons:**
- Network latency
- Requires separate server

## Model Files

The download script fetches:
- `params.json` - Model configuration
- `consolidated.safetensors` - Model weights (safetensors format)
- `tokenizer.model.v3` - Tokenizer model

## Memory Requirements

- **7B Model (FP16)**: ~14GB GPU memory
- **7B Model (FP32)**: ~28GB GPU memory
- **CPU Inference**: Slower but works with sufficient RAM

## Performance Tips

1. **Use GPU**: Set `MISTRAL_DEVICE=cuda` for faster inference
2. **Use FP16**: Automatically used on GPU for memory efficiency
3. **Batch Processing**: The system handles requests sequentially
4. **Context Window**: Mistral-7B supports up to 32K tokens, but 8K is recommended for this use case

## Troubleshooting

### Out of Memory Error
- Reduce batch size
- Use CPU inference: `MISTRAL_DEVICE=cpu`
- Use API mode with a separate server

### Slow Inference
- Ensure GPU is available: `python -c "import torch; print(torch.cuda.is_available())"`
- Check GPU memory: `nvidia-smi`
- Consider using API mode with optimized server (vLLM)

### Model Not Found
- Check `MISTRAL_MODEL_PATH` points to correct directory
- Re-run download script
- Or let it auto-download from Hugging Face (slower first time)

## Testing

Test the integration:

```python
from app.llm.mistral_client import call_mistral

response = call_mistral("Hello, how are you?")
print(response)
```

## Switching Back to GPT-OSS

Simply change in `.env`:
```bash
LLM_PROVIDER=gpt-oss
```

The system will automatically use the configured provider.


