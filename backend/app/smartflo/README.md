# Tata Smartflo Bi-Directional Audio Streaming Integration

## Overview

This module implements a complete WebSocket server acting as a Vendor for Tata Smartflo's Bi-Directional Audio Streaming API. The implementation follows best practices with proper design patterns, Pydantic validation, and comprehensive audio codec support.

## Architecture

### Directory Structure

```
smartflo/
├── __init__.py
├── websocket_server.py       # Main WebSocket server
├── schemas/
│   ├── __init__.py
│   ├── incoming.py            # Pydantic models for Smartflo → Vendor events
│   └── outgoing.py            # Pydantic models and Builder for Vendor → Smartflo events
├── core/
│   ├── __init__.py
│   ├── session_manager.py     # Per-stream session state management
│   ├── router.py              # Event routing and dispatching
│   └── middleware.py          # Validation, logging, exception handling
├── audio/
│   ├── __init__.py
│   ├── codec.py               # μ-law ↔ PCM16 conversion
│   └── processor.py           # Audio processing stubs
└── handlers/
    ├── __init__.py
    ├── start_handler.py       # Handle start events
    ├── media_handler.py       # Handle media events
    ├── stop_handler.py        # Handle stop events
    ├── dtmf_handler.py        # Handle DTMF events
    └── mark_handler.py        # Handle mark events
```

### Design Patterns Used

1. **Factory Pattern**: `parse_incoming_event()` creates appropriate event objects based on type
2. **Builder Pattern**: `EventBuilder` constructs outgoing events with fluent interface
3. **Router Pattern**: Event dispatching based on event type
4. **Middleware Pipeline**: Request processing through validation, logging, error handling
5. **Session Management**: Per-stream state tracking with thread-safe operations

## Features

### ✅ Incoming Event Schemas (Smartflo → Vendor)

All incoming events are validated using Pydantic models:

- **StartEvent**: Call/stream initialization
- **MediaEvent**: Audio chunks (base64 encoded μ-law)
- **StopEvent**: Call/stream termination
- **DTMFEvent**: DTMF key presses
- **MarkEvent**: Playback acknowledgments

### ✅ Outgoing Event Schemas (Vendor → Smartflo)

Built using the EventBuilder pattern:

- **ConnectedEvent**: Sent immediately after connection
- **VendorMediaEvent**: Send audio back to Smartflo
- **ClearEvent**: Clear Smartflo's audio buffer
- **VendorMarkEvent**: Mark playback points

### ✅ Audio Codec Support

- μ-law (G.711) ↔ PCM16 conversion
- Base64 encoding/decoding
- 8000 Hz, mono, 8-bit μ-law format
- Proper handling of audio streams

### ✅ Session Management

Each call maintains:
- Unique stream and call identifiers
- Monotonically increasing sequence numbers
- Audio buffer
- Metadata and timestamps
- Thread-safe operations

### ✅ WebSocket Server

Complete implementation with:
- Connection handling
- Immediate "connected" event
- Event validation and routing
- Graceful error handling
- Session lifecycle management

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start the server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The Smartflo endpoint will be available at: `ws://localhost:8000/vendor-stream`

## Usage

### WebSocket Endpoint

**URL**: `/vendor-stream`

**Protocol**: WebSocket

**Description**: Accepts connections from Tata Smartflo for bi-directional audio streaming

### Event Flow

1. **Connection**
   - Smartflo connects to `/vendor-stream`
   - Server accepts and sends `connected` event

2. **Start Event**
   - Smartflo sends `start` event with call metadata
   - Server creates session and stores metadata

3. **Media Events**
   - Smartflo continuously sends `media` events with audio chunks
   - Server decodes μ-law, processes audio
   - Server can send media back using `VendorMediaEvent`

4. **DTMF Events** (Optional)
   - Smartflo sends `dtmf` when user presses keys
   - Server processes for IVR or input collection

5. **Mark Events** (Optional)
   - Used for synchronization and playback tracking
   - Bi-directional acknowledgments

6. **Stop Event**
   - Smartflo sends `stop` when call ends
   - Server cleans up session and resources

## Example Messages

### From Smartflo (Incoming)

#### Start Event
```json
{
  "event": "start",
  "sequenceNumber": "1",
  "streamSid": "ST123456789",
  "start": {
    "callSid": "CA123456789",
    "streamSid": "ST123456789",
    "accountSid": "AC123456789",
    "tracks": "inbound",
    "customParameters": {},
    "mediaFormat": {
      "encoding": "audio/x-mulaw",
      "sampleRate": 8000,
      "channels": 1
    }
  }
}
```

#### Media Event
```json
{
  "event": "media",
  "sequenceNumber": "2",
  "streamSid": "ST123456789",
  "media": {
    "payload": "base64_encoded_mulaw_audio_data...",
    "chunk": "1",
    "timestamp": "1234567890"
  }
}
```

#### Stop Event
```json
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

### To Smartflo (Outgoing)

#### Connected Event
```json
{
  "event": "connected",
  "protocol": "Call",
  "version": "1.0.0"
}
```

#### Media Event (Response)
```json
{
  "event": "media",
  "streamSid": "ST123456789",
  "sequenceNumber": 1,
  "media": {
    "payload": "base64_encoded_mulaw_audio_data..."
  }
}
```

#### Mark Event
```json
{
  "event": "mark",
  "streamSid": "ST123456789",
  "sequenceNumber": 2,
  "mark": {
    "name": "playback_complete"
  }
}
```

## Code Examples

### Using the Event Builder

```python
from smartflo.schemas.outgoing import EventBuilder

# Build a media event
event = (EventBuilder()
        .type("media")
        .sid("ST123456789")
        .sequence(1)
        .payload(payload="base64_audio_data")
        .build())

# Build a mark event
mark_event = (EventBuilder()
             .type("mark")
             .sid("ST123456789")
             .sequence(2)
             .payload(name="playback_done")
             .build())
```

### Parsing Incoming Events

```python
from smartflo.schemas.incoming import parse_incoming_event

raw_json = {
    "event": "start",
    "sequenceNumber": "1",
    "streamSid": "ST123456789",
    "start": {...}
}

event = parse_incoming_event(raw_json)
# Returns: StartEvent instance with validated data
```

### Audio Processing

```python
from smartflo.audio import decode_mulaw_from_base64, encode_pcm16_to_mulaw_base64

# Decode incoming audio
pcm_audio = decode_mulaw_from_base64(base64_mulaw_data)

# Process PCM audio...

# Encode response audio
base64_mulaw = encode_pcm16_to_mulaw_base64(pcm_audio)
```

### Session Management

```python
from smartflo.core import session_manager

# Create session
session = await session_manager.create_session("ST123", "CA123")

# Get next sequence number
seq = session.next_sequence()

# Update metadata
session.update_metadata(user_id="user123", language="en")

# Cleanup
await session_manager.delete_session("ST123")
```

## Extending the Implementation

### Custom Audio Processing

Replace the stubs in `audio/processor.py`:

```python
async def process_incoming_audio(pcm_bytes: bytes, stream_sid: str) -> None:
    # Add your ASR/VAD/ML processing here
    transcript = await your_asr_service(pcm_bytes)
    # Handle the transcript...

async def generate_response_audio(text: str, stream_sid: str) -> Optional[bytes]:
    # Add your TTS logic here
    audio_bytes = await your_tts_service(text)
    return audio_bytes
```

### Custom Event Handlers

Add new handlers or modify existing ones:

```python
from smartflo.core.router import router
from smartflo.core.middleware import exception_handler

@router.route("custom_event")
@exception_handler
async def handle_custom(event, websocket, **kwargs):
    # Your custom logic here
    pass
```

### Sending Audio Back to Smartflo

In your handler, use the server instance:

```python
async def handle_media(event, websocket, **kwargs):
    server = kwargs['server']
    session = await session_manager.get_session(event.streamSid)
    
    # Generate response audio
    pcm_audio = await generate_response_audio("Hello", event.streamSid)
    if pcm_audio:
        base64_audio = encode_pcm16_to_mulaw_base64(pcm_audio)
        seq = session.next_sequence()
        
        await server.send_media_event(
            websocket,
            event.streamSid,
            seq,
            base64_audio
        )
```

## Logging

The module uses Python's standard logging framework:

- **INFO**: Connection events, session lifecycle
- **DEBUG**: Event details, audio processing
- **WARNING**: Missing sessions, validation issues
- **ERROR**: Exceptions, handler errors

Configure logging level in your application:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Testing

### Manual Testing with WebSocket Client

```python
import asyncio
import websockets
import json

async def test_smartflo():
    uri = "ws://localhost:8000/vendor-stream"
    
    async with websockets.connect(uri) as websocket:
        # Receive connected event
        response = await websocket.recv()
        print(f"Received: {response}")
        
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
        await websocket.send(json.dumps(start_event))
        
        # Send media event
        media_event = {
            "event": "media",
            "sequenceNumber": "2",
            "streamSid": "ST_TEST_123",
            "media": {
                "payload": "AAECAwQFBgc=",  # Sample base64
                "chunk": "1",
                "timestamp": "1234567890"
            }
        }
        await websocket.send(json.dumps(media_event))
        
        # Send stop event
        stop_event = {
            "event": "stop",
            "sequenceNumber": "3",
            "streamSid": "ST_TEST_123",
            "stop": {
                "callSid": "CA_TEST_123",
                "streamSid": "ST_TEST_123"
            }
        }
        await websocket.send(json.dumps(stop_event))

asyncio.run(test_smartflo())
```

## Security Considerations

1. **Authentication**: Add authentication middleware if needed
2. **Rate Limiting**: Implement rate limiting for production
3. **Input Validation**: All inputs are validated via Pydantic
4. **Error Handling**: Comprehensive exception handling prevents crashes
5. **Resource Cleanup**: Sessions are properly cleaned up

## Performance

- Async/await for concurrent handling
- Thread-safe session management
- Efficient audio codec operations
- Minimal memory footprint

## Troubleshooting

### Connection Issues
- Verify WebSocket URL: `ws://your-server:8000/vendor-stream`
- Check firewall settings
- Review server logs

### Audio Quality Issues
- Verify μ-law encoding (8-bit, 8000 Hz)
- Check base64 encoding/decoding
- Monitor audio buffer sizes

### Session Issues
- Check session creation in logs
- Verify streamSid consistency
- Monitor sequence numbers

## API Reference

For detailed API documentation, see:
- `schemas/incoming.py` - Incoming event models
- `schemas/outgoing.py` - Outgoing event models and builder
- `websocket_server.py` - WebSocket server API
- `core/session_manager.py` - Session management API

## License

Part of the VAANI-2.0-STREAM project.

## Support

For issues and questions:
- Check logs for detailed error messages
- Review example messages
- Verify Pydantic validation errors
