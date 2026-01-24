# Smartflo Integration - Quick Start Guide

## Installation

The Smartflo module is already integrated into the VAANI-2.0-STREAM application. No additional installation is required beyond the standard requirements.

## Starting the Server

```bash
# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000

# Or with reload for development
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The Smartflo endpoint will be available at:
```
ws://your-server:8000/vendor-stream
```

## Testing the Integration

### Option 1: Using the Example Test Client

Run the provided test client:

```bash
# Make sure the server is running first
python smartflo/example_test.py
```

This will:
- Connect to the WebSocket endpoint
- Send a complete flow of events (start, media, dtmf, mark, stop)
- Test multiple concurrent sessions
- Test error handling

### Option 2: Using the Minimal Integration Test

```bash
# This creates a minimal FastAPI app with just the Smartflo endpoint
uvicorn smartflo.test_integration:test_app --host 0.0.0.0 --port 8000
```

### Option 3: Manual Testing with Python

```python
import asyncio
import websockets
import json

async def test_connection():
    uri = "ws://localhost:8000/vendor-stream"
    
    async with websockets.connect(uri) as ws:
        # Receive connected event
        response = await ws.recv()
        print(f"Connected: {response}")
        
        # Send start event
        start_event = {
            "event": "start",
            "sequenceNumber": "1",
            "streamSid": "ST_TEST_123",
            "start": {
                "callSid": "CA_TEST_123",
                "streamSid": "ST_TEST_123"
            }
        }
        await ws.send(json.dumps(start_event))
        print("Sent start event")

asyncio.run(test_connection())
```

## Configuration with Tata Smartflo

### Step 1: Configure Smartflo Dashboard

In your Tata Smartflo dashboard:

1. Go to your application settings
2. Configure the WebSocket URL:
   ```
   wss://your-domain.com/vendor-stream
   ```
   (Use `wss://` for production with SSL)

3. Set the following parameters:
   - Protocol: WebSocket
   - Audio Format: μ-law (G.711)
   - Sample Rate: 8000 Hz
   - Channels: Mono (1)

### Step 2: SSL/TLS Configuration (Production)

For production, use a reverse proxy (nginx) with SSL:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /vendor-stream {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
```

## Event Flow

### 1. Connection Established
```
Client → Server: WebSocket connection
Server → Client: {"event": "connected", "protocol": "Call", "version": "1.0.0"}
```

### 2. Call Start
```
Client → Server: 
{
  "event": "start",
  "sequenceNumber": "1",
  "streamSid": "ST123456789",
  "start": {
    "callSid": "CA123456789",
    "streamSid": "ST123456789",
    "accountSid": "AC123456789",
    "tracks": "inbound",
    "mediaFormat": {
      "encoding": "audio/x-mulaw",
      "sampleRate": 8000,
      "channels": 1
    }
  }
}
```

Server creates session and prepares audio processing.

### 3. Audio Streaming
```
Client → Server: 
{
  "event": "media",
  "sequenceNumber": "2",
  "streamSid": "ST123456789",
  "media": {
    "payload": "base64_encoded_mulaw_audio...",
    "chunk": "1",
    "timestamp": "1234567890"
  }
}
```

Server decodes audio, processes it, and can optionally send audio back:

```
Server → Client:
{
  "event": "media",
  "sequenceNumber": 1,
  "streamSid": "ST123456789",
  "media": {
    "payload": "base64_encoded_mulaw_audio..."
  }
}
```

### 4. DTMF Events (Optional)
```
Client → Server:
{
  "event": "dtmf",
  "sequenceNumber": "10",
  "streamSid": "ST123456789",
  "dtmf": {
    "digit": "1",
    "track": "inbound"
  }
}
```

### 5. Mark Events (Optional)
```
Server → Client:
{
  "event": "mark",
  "sequenceNumber": 5,
  "streamSid": "ST123456789",
  "mark": {
    "name": "playback_complete"
  }
}
```

### 6. Call End
```
Client → Server:
{
  "event": "stop",
  "sequenceNumber": "999",
  "streamSid": "ST123456789",
  "stop": {
    "callSid": "CA123456789",
    "streamSid": "ST123456789"
  }
}
```

Server cleans up session and resources.

## Customizing Audio Processing

### Replace Audio Processor Stubs

Edit `smartflo/audio/processor.py`:

```python
async def process_incoming_audio(pcm_bytes: bytes, stream_sid: str) -> None:
    """
    Process incoming audio from caller.
    Replace this with your actual audio processing.
    """
    # Example: Send to ASR
    from services.asr_service import transcribe_audio
    transcript = await transcribe_audio(pcm_bytes)
    
    # Example: Process with LLM
    from services.llm_service import generate_response
    response_text = await generate_response(transcript)
    
    # Example: Generate audio response
    audio = await generate_response_audio(response_text, stream_sid)
    if audio:
        # Send audio back to Smartflo
        from smartflo.core.session_manager import session_manager
        from smartflo.audio.codec import encode_pcm16_to_mulaw_base64
        
        session = await session_manager.get_session(stream_sid)
        if session:
            base64_audio = encode_pcm16_to_mulaw_base64(audio)
            # Use the server to send media event
            # (You'll need to store WebSocket reference in session)
```

### Send Audio Back to Caller

In your handler, use the server instance:

```python
from smartflo.websocket_server import smartflo_server
from smartflo.audio.codec import encode_pcm16_to_mulaw_base64

# Generate or retrieve audio
pcm_audio = await your_tts_service.generate(text)

# Encode to μ-law + base64
base64_audio = encode_pcm16_to_mulaw_base64(pcm_audio)

# Get session for sequence number
session = await session_manager.get_session(stream_sid)
seq = session.next_sequence()

# Send media event
await smartflo_server.send_media_event(
    websocket,
    stream_sid,
    seq,
    base64_audio
)
```

### Send Mark Event After Playback

```python
# After sending all audio chunks for a response
seq = session.next_sequence()
await smartflo_server.send_mark_event(
    websocket,
    stream_sid,
    seq,
    "response_complete"
)
```

### Clear Audio Buffer

```python
# To interrupt and clear Smartflo's audio buffer
await smartflo_server.send_clear_event(websocket, stream_sid)
```

## Monitoring and Logging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Access Session Information

```python
from smartflo.core.session_manager import session_manager

# Get session
session = await session_manager.get_session("ST123456789")

# Access session data
print(f"Call SID: {session.call_sid}")
print(f"Stream SID: {session.stream_sid}")
print(f"Sequence: {session.sequence_counter}")
print(f"Audio buffer size: {len(session.audio_buffer)}")
print(f"Metadata: {session.metadata}")

# Get all active sessions
all_sessions = await session_manager.get_all_sessions()
print(f"Active sessions: {len(all_sessions)}")
```

## Troubleshooting

### Connection Issues

**Problem**: WebSocket connection fails

**Solutions**:
- Verify server is running: `curl http://localhost:8000/health`
- Check firewall rules
- For SSL: Verify certificate is valid
- Check Smartflo dashboard URL configuration

### Audio Quality Issues

**Problem**: Audio sounds distorted or choppy

**Solutions**:
- Verify μ-law encoding (8-bit, 8000 Hz)
- Check base64 encoding is correct
- Monitor audio buffer sizes in logs
- Verify network latency is acceptable

### Session Not Found Errors

**Problem**: "Received media for unknown session"

**Solutions**:
- Ensure start event is received before media events
- Check streamSid consistency across events
- Monitor session creation in logs
- Check session cleanup isn't happening too early

### Memory Issues

**Problem**: High memory usage

**Solutions**:
- Clear audio buffers periodically:
  ```python
  await session.clear_audio_buffer()
  ```
- Clean up inactive sessions:
  ```python
  await session_manager.cleanup_inactive_sessions(timeout_seconds=3600)
  ```
- Limit audio buffer size in your handlers

## Performance Optimization

### Concurrent Sessions

The server supports multiple concurrent sessions. Each session is isolated with its own state.

### Audio Processing

For better performance:
1. Process audio in chunks asynchronously
2. Use asyncio queues for audio pipeline
3. Consider worker processes for heavy ML models
4. Cache TTS responses for common phrases

### Monitoring

Add custom metrics:

```python
from smartflo.core.session_manager import session_manager
import time

async def get_metrics():
    sessions = await session_manager.get_all_sessions()
    return {
        "active_sessions": len(sessions),
        "total_audio_bytes": sum(
            len(s.audio_buffer) for s in sessions.values()
        ),
        "timestamp": time.time()
    }
```

## Security Considerations

### Authentication

Add authentication middleware if needed:

```python
from fastapi import Header, HTTPException

@app.websocket("/vendor-stream")
async def vendor_stream(
    websocket: WebSocket,
    authorization: str = Header(None)
):
    # Verify authorization
    if not verify_token(authorization):
        await websocket.close(code=1008)  # Policy Violation
        return
    
    await smartflo_server.handle_socket(websocket)
```

### Rate Limiting

Implement rate limiting to prevent abuse:

```python
from collections import defaultdict
from time import time

connection_counts = defaultdict(list)

@app.websocket("/vendor-stream")
async def vendor_stream(websocket: WebSocket):
    client_ip = websocket.client.host
    
    # Check rate limit
    now = time()
    connection_counts[client_ip] = [
        t for t in connection_counts[client_ip]
        if now - t < 60  # 1 minute window
    ]
    
    if len(connection_counts[client_ip]) > 10:  # Max 10 connections per minute
        await websocket.close(code=1008)
        return
    
    connection_counts[client_ip].append(now)
    await smartflo_server.handle_socket(websocket)
```

## Support and Documentation

- Full API Documentation: See `smartflo/README.md`
- Example Test Client: `smartflo/example_test.py`
- Integration Test: `smartflo/test_integration.py`
- Smartflo Official Docs: https://docs.smartflo.tatatelebusiness.com/

## Next Steps

1. ✅ Server is running and ready
2. Configure Smartflo dashboard with your WebSocket URL
3. Make a test call to verify the integration
4. Customize audio processing for your use case
5. Add authentication and security
6. Deploy to production with SSL/TLS
7. Monitor and optimize performance

For questions or issues, check the logs and ensure all events are being sent/received correctly.
