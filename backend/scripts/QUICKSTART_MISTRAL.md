# Quick Start: Mistral Server on Port 5001

## Step 1: Start the Mistral Server

### Option A: Using the shell script (Recommended)
```bash
cd backend/scripts
./run_mistral_server.sh
```

### Option B: Using Python directly
```bash
cd backend
python3 scripts/start_mistral_server.py
```

### Option C: Using environment variables
```bash
export MISTRAL_PORT=5001
export MISTRAL_HOST=0.0.0.0
export MISTRAL_MODEL_PATH=~/mistral_models/7B-Instruct-v0.3
export MISTRAL_DEVICE=cuda  # or "cpu"

python3 backend/scripts/start_mistral_server.py
```

## Step 2: Verify Server is Running

The server will start on `http://0.0.0.0:5001` (accessible via `http://192.168.30.121:5001`). You should see:
```
✅ Model loaded successfully on cuda
✅ Server ready on http://0.0.0.0:5001
```

Test the server:
```bash
curl http://192.168.30.121:5001/health
```

Expected response:
```json
{"status": "healthy", "model_loaded": true}
```

## Step 3: Configure Your Application

Add to your `.env` file:
```bash
# Use Mistral as LLM provider
LLM_PROVIDER=mistral

# Use API mode (server on port 5001)
MISTRAL_USE_API=true
MISTRAL_API_BASE=http://192.168.30.121:5001
MISTRAL_API_KEY=local
```

## Step 4: Test the API

### Test with curl:
```bash
curl -X POST http://192.168.30.121:5001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local" \
  -d '{
    "model": "mistral-7b-instruct",
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ],
    "temperature": 0.1,
    "max_tokens": 100
  }'
```

### Test with Python:
```python
import httpx

response = httpx.post(
    "http://192.168.30.121:5001/v1/chat/completions",
    headers={"Authorization": "Bearer local"},
    json={
        "model": "mistral-7b-instruct",
        "messages": [{"role": "user", "content": "Hello!"}],
        "temperature": 0.1
    }
)
print(response.json())
```

## Troubleshooting

### Port Already in Use
If port 5001 is already in use:
```bash
export MISTRAL_PORT=5002  # Use different port
python3 backend/scripts/start_mistral_server.py
```

### Out of Memory
- Use CPU mode: `export MISTRAL_DEVICE=cpu`
- Reduce max_tokens in requests
- Use a smaller model or quantized version

### Model Not Found
- Check model path: `ls ~/mistral_models/7B-Instruct-v0.3`
- Re-download: `python3 backend/scripts/download_mistral_model.py`

### Slow Inference
- Ensure GPU is available: `nvidia-smi`
- Check device: Server logs will show "Device: cuda" or "Device: cpu"
- GPU inference is ~10-100x faster than CPU

## Running in Background

### Using nohup:
```bash
nohup python3 backend/scripts/start_mistral_server.py > mistral_server.log 2>&1 &
```

### Using screen:
```bash
screen -S mistral_server
python3 backend/scripts/start_mistral_server.py
# Press Ctrl+A then D to detach
```

### Using systemd (Linux):
Create `/etc/systemd/system/mistral-server.service`:
```ini
[Unit]
Description=Mistral-7B Inference Server
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/LTFS_Conversational_Flow/backend
Environment="MISTRAL_PORT=5001"
Environment="MISTRAL_DEVICE=cuda"
ExecStart=/path/to/venv/bin/python scripts/start_mistral_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable mistral-server
sudo systemctl start mistral-server
sudo systemctl status mistral-server
```

## API Endpoints

- `GET /` - Server info and health
- `GET /health` - Health check
- `GET /v1/models` - List available models
- `POST /v1/chat/completions` - Chat completions (OpenAI-compatible)

## Next Steps

Once the server is running, your LTFS Conversational Flow application will automatically use it when configured with:
```bash
LLM_PROVIDER=mistral
MISTRAL_USE_API=true
MISTRAL_API_BASE=http://192.168.30.121:5001
```

The application will route all LLM calls through this server!


