# Tata Smartflo Integration - Quick Reference

## 🚀 Quick Start

```bash
# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000

# Run test client
python smartflo/example_test.py
```

## 🔗 Endpoint

```
ws://localhost:8000/vendor-stream
```

## 📨 Event Types

### Incoming (Smartflo → Vendor)
- `start` - Call begins
- `media` - Audio chunks
- `stop` - Call ends
- `dtmf` - Key press
- `mark` - Acknowledgment

### Outgoing (Vendor → Smartflo)
- `connected` - Connection OK
- `media` - Send audio
- `mark` - Playback point
- `clear` - Clear buffer

## 💻 Code Examples

### Parse Incoming Event
```python
from smartflo.schemas.incoming import parse_incoming_event

event = parse_incoming_event(json_data)
# Returns: StartEvent, MediaEvent, StopEvent, DTMFEvent, or MarkEvent
```

### Build Outgoing Event
```python
from smartflo.schemas.outgoing import EventBuilder

# Connected event
connected = EventBuilder().type("connected").build()

# Media event
media = (EventBuilder()
        .type("media")
        .sid(stream_sid)
        .sequence(1)
        .payload(payload=base64_audio)
        .build())
```

### Audio Codec
```python
from smartflo.audio import (
    decode_mulaw_from_base64,
    encode_pcm16_to_mulaw_base64
)

# Decode incoming audio
pcm_bytes = decode_mulaw_from_base64(event.media.payload)

# Encode outgoing audio
base64_audio = encode_pcm16_to_mulaw_base64(pcm_bytes)
```

### Session Management
```python
from smartflo.core import session_manager

# Create session
session = await session_manager.create_session(stream_sid, call_sid)

# Get next sequence number
seq = session.next_sequence()

# Store metadata
session.update_metadata(language="en", user_id="123")

# Clean up
await session_manager.delete_session(stream_sid)
```

### Send Events
```python
from smartflo.websocket_server import smartflo_server

# Send media
await smartflo_server.send_media_event(
    websocket,
    stream_sid,
    sequence_number,
    base64_audio
)

# Send mark
await smartflo_server.send_mark_event(
    websocket,
    stream_sid,
    sequence_number,
    "playback_complete"
)

# Clear buffer
await smartflo_server.send_clear_event(websocket, stream_sid)
```

## 🔧 Custom Audio Processing

Edit `smartflo/audio/processor.py`:

```python
async def process_incoming_audio(pcm_bytes: bytes, stream_sid: str):
    # Your ASR/VAD/ML processing here
    transcript = await your_asr_service(pcm_bytes)
    return transcript

async def generate_response_audio(text: str, stream_sid: str):
    # Your TTS here
    audio = await your_tts_service(text)
    return audio  # Return PCM16 bytes
```

## 📊 Event Flow

```
1. Client connects → Server sends "connected"
2. Client sends "start" → Server creates session
3. Client sends "media" → Server processes audio
4. Server sends "media" → Client plays audio
5. Server sends "mark" → Client acknowledges
6. Client sends "stop" → Server cleans up
```

## 🐛 Troubleshooting

### Connection fails
```bash
# Check server is running
curl http://localhost:8000/health

# Check logs
tail -f server.log
```

### Audio quality issues
- Verify μ-law encoding (8-bit, 8000 Hz)
- Check base64 encoding is correct
- Monitor buffer sizes

### Session not found
- Ensure start event is sent first
- Check streamSid consistency
- Monitor session creation in logs

## 📚 Documentation

- **Architecture**: `smartflo/README.md`
- **Usage Guide**: `smartflo/USAGE.md`
- **Implementation**: `smartflo/IMPLEMENTATION_SUMMARY.md`
- **Examples**: `smartflo/example_test.py`

## 🔐 Security (Production)

```python
# Add authentication
@app.websocket("/vendor-stream")
async def vendor_stream(
    websocket: WebSocket,
    token: str = Query(...)
):
    if not verify_token(token):
        await websocket.close(code=1008)
        return
    await smartflo_server.handle_socket(websocket)
```

## 📈 Monitoring

```python
from smartflo.core import session_manager

# Get active sessions
sessions = await session_manager.get_all_sessions()
print(f"Active sessions: {len(sessions)}")

# Get session stats
session = await session_manager.get_session(stream_sid)
print(f"Buffer: {len(session.audio_buffer)} bytes")
print(f"Events: {session.sequence_counter}")
```

## 🎯 Key Features

✅ Full Pydantic validation
✅ Builder pattern for events
✅ μ-law audio codec
✅ Session management
✅ Event routing
✅ Middleware pipeline
✅ Comprehensive logging
✅ Production ready

## 📞 Support

For issues:
1. Check logs (INFO, DEBUG, ERROR levels)
2. Review documentation
3. Run test client
4. Verify event structure

## 🌐 Smartflo Configuration

In Smartflo dashboard:
- WebSocket URL: `wss://your-domain.com/vendor-stream`
- Protocol: WebSocket
- Audio: μ-law, 8000 Hz, mono

## ⚡ Performance Tips

1. Process audio asynchronously
2. Use asyncio queues for pipelines
3. Clear buffers periodically
4. Monitor memory usage
5. Clean up inactive sessions

## 📝 Common Patterns

### IVR Menu
```python
@handle_dtmf
async def handle_dtmf(event, websocket, **kwargs):
    digit = event.dtmf.digit
    if digit == "1":
        # Play option 1 audio
        pass
```

### Audio Response
```python
# Generate response
response_audio = await generate_response_audio("Hello", stream_sid)

# Encode and send
base64_audio = encode_pcm16_to_mulaw_base64(response_audio)
seq = session.next_sequence()
await smartflo_server.send_media_event(
    websocket, stream_sid, seq, base64_audio
)
```

### Mark After Playback
```python
# After sending all audio chunks
seq = session.next_sequence()
await smartflo_server.send_mark_event(
    websocket, stream_sid, seq, "response_complete"
)
```

---

**Ready to use!** Start the server and connect Smartflo to `/vendor-stream`.
