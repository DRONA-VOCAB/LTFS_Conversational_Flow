# Smartflo + VAANI Integration - Visual Guide

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        VAANI-2.0-STREAM Server                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌────────────────┐                    ┌────────────────┐          │
│  │  Web UI        │                    │  Smartflo      │          │
│  │  WebSocket     │                    │  WebSocket     │          │
│  │  /ws/audio     │                    │  /vendor-stream│          │
│  └────────┬───────┘                    └────────┬───────┘          │
│           │                                     │                   │
│           │ raw PCM audio                       │ μ-law base64      │
│           ▼                                     ▼                   │
│  ┌────────────────┐                    ┌────────────────┐          │
│  │  VAD           │                    │  Media Handler │          │
│  │  (process_frame)│                   │  - Decode base64│         │
│  └────────┬───────┘                    │  - μ-law→PCM16 │          │
│           │                             └────────┬───────┘          │
│           │ PCM16 chunks                         │ PCM16            │
│           │                                      │                  │
│           └──────────────┬───────────────────────┘                  │
│                          ▼                                          │
│                 ┌─────────────────┐                                │
│                 │   ASR Queue     │                                │
│                 │  (audio bytes)  │                                │
│                 └────────┬────────┘                                │
│                          ▼                                          │
│                 ┌─────────────────┐                                │
│                 │  ASR Service    │                                │
│                 │  (transcribe)   │                                │
│                 └────────┬────────┘                                │
│                          ▼ transcribed text                         │
│                 ┌─────────────────┐                                │
│                 │   LLM Queue     │                                │
│                 │    (text)       │                                │
│                 └────────┬────────┘                                │
│                          ▼                                          │
│                 ┌─────────────────┐                                │
│                 │  LLM Service    │                                │
│                 │  (generate)     │                                │
│                 └────────┬────────┘                                │
│                          ▼ response text                            │
│                 ┌─────────────────┐                                │
│                 │   TTS Queue     │                                │
│                 │    (text)       │                                │
│                 └────────┬────────┘                                │
│                          ▼                                          │
│                 ┌─────────────────┐                                │
│                 │  TTS Service    │                                │
│                 │  (synthesize)   │                                │
│                 └────────┬────────┘                                │
│                          │ PCM16 audio                              │
│           ┌──────────────┴───────────────┐                         │
│           ▼ raw PCM                      ▼ μ-law base64            │
│  ┌────────────────┐            ┌────────────────┐                 │
│  │  Web UI        │            │  Smartflo      │                 │
│  │  send_bytes()  │            │  Integration   │                 │
│  │                │            │  - PCM16→μ-law │                 │
│  │                │            │  - base64 encode│                │
│  │                │            │  - media event  │                │
│  └────────────────┘            └────────────────┘                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Audio Flow Details

### Incoming Audio (Caller → Bot)

#### Smartflo Path
```
Smartflo Call
    │
    ├─ μ-law encoded (8000 Hz, mono, 8-bit)
    │
    ├─ Base64 encoded string
    │
    ├─ Media Event JSON: {"event":"media", "media":{"payload":"..."}}
    │
    ▼
Media Handler (smartflo/handlers/media_handler.py)
    │
    ├─ Decode: base64 → raw μ-law bytes
    │
    ├─ Convert: μ-law → PCM16 (using audioop)
    │
    ▼
ASR Queue (queues/asr_queue.py)
    │
    ├─ Format: (websocket, pcm_bytes, stream_sid)
    │
    ▼
[Same pipeline as Web UI from here]
```

#### Web UI Path
```
Browser Microphone
    │
    ├─ Raw PCM audio
    │
    ▼
VAD (services/vad/)
    │
    ├─ Detect speech activity
    │
    ├─ Buffer audio chunks
    │
    ▼
ASR Queue (queues/asr_queue.py)
    │
    ├─ Format: (websocket, pcm_bytes, utterance_id)
    │
    ▼
[Common pipeline]
```

### Outgoing Audio (Bot → Caller)

#### Common Pipeline
```
TTS Queue
    │
    ├─ Format: (websocket, text, utterance_id)
    │
    ▼
TTS Service (services/tts_service_rest.py)
    │
    ├─ Generate PCM16 audio from text
    │
    ├─ Detect connection type:
    │   • Check websocket.scope['path']
    │   • '/vendor-stream' → Smartflo
    │   • '/voice' → Web UI
    │
    ├─ Branch based on type
    │
    ▼
```

#### Smartflo Output Path
```
TTS Service (if is_smartflo_connection)
    │
    ├─ Collect all audio chunks
    │
    ▼
Smartflo Integration (smartflo/integration.py)
    │
    ├─ Convert: PCM16 → μ-law
    │
    ├─ Encode: μ-law → base64 string
    │
    ├─ Build Smartflo media event
    │   • Get sequence number from session
    │   • Create media payload
    │
    ▼
Smartflo WebSocket
    │
    ├─ Send: {"event":"media", "sequenceNumber":X, "media":{"payload":"..."}}
    │
    ▼
Smartflo → Caller's Phone
```

#### Web UI Output Path
```
TTS Service (if NOT smartflo)
    │
    ├─ Stream audio chunks immediately
    │
    ├─ Send JSON events: tts_start, end
    │
    ▼
Web UI WebSocket
    │
    ├─ send_bytes(chunk) for each chunk
    │
    ▼
Browser → Speakers
```

## Key Components

### 1. smartflo/integration.py
- **is_smartflo_connection()**: Detect Smartflo vs Web UI
- **send_audio_to_smartflo()**: Convert & send audio to Smartflo
- **get_stream_sid_for_websocket()**: Lookup stream identifier

### 2. smartflo/audio/processor.py
- **process_incoming_audio()**: Route to ASR queue
- Passes websocket reference through pipeline

### 3. smartflo/handlers/media_handler.py
- Receives Smartflo media events
- Decodes μ-law audio
- Feeds into queue system

### 4. services/tts_service_rest.py
- Enhanced to handle both protocols
- Auto-detects connection type
- Routes output appropriately

## Data Flow Summary

```
┌──────────────┐
│   Smartflo   │ ←─ μ-law base64 ─── TTS Svc (encode) ← PCM16
│              │                           ↑
│  /vendor-    │                      TTS Queue
│   stream     │                           ↑
│              │                      LLM Svc
│              │                           ↑
│              │                      LLM Queue
│              │                           ↑
│              │                      ASR Svc
└──────────────┘                           ↑
       │                              ASR Queue
       │ μ-law base64                      ↑
       │                       ┌───────────┴────────┐
       ▼                       │                    │
  Media Handler ───PCM16──────►│                    │
                               │                    │
┌──────────────┐              │    Common Queue    │
│   Web UI     │ ←── PCM16 ─── TTS Svc (stream)    │
│              │                    ↑               │
│   /voice     │                    │               │
│              │                    │               │
│              │              [Same Pipeline]       │
└──────────────┘                    │               │
       │                            │               │
       │ raw PCM                    │               │
       ▼                            │               │
     VAD ──────PCM16───────────────┴───────────────┘
```

## Configuration

No additional config needed! The system automatically:
1. Detects connection type from WebSocket path
2. Converts audio formats appropriately
3. Routes through shared queue pipeline
4. Sends responses in correct format

## Benefits

✅ **Unified Services**: One ASR/LLM/TTS for all clients
✅ **No Duplication**: Reuse existing queue architecture
✅ **Automatic Detection**: Smart routing based on connection
✅ **Format Agnostic**: Transparent audio conversions
✅ **Backward Compatible**: Web UI works unchanged
✅ **Scalable**: Queue system handles multiple clients

## Testing

```bash
# Terminal 1: Start server
uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2: Test Smartflo
python smartflo/example_test.py

# Terminal 3: Test Web UI (if available)
# Open browser to http://localhost:8000
```

## Logs to Watch

```
# Smartflo incoming
Smartflo audio (X bytes) queued for ASR processing

# ASR processing
ASR received X bytes of audio data

# LLM processing
LLM received text: "hello world"

# TTS generation
Connection type: Smartflo
Sent audio to Smartflo (stream: ST123)
```

## Troubleshooting

**Q: Audio not being processed?**
- Check logs for "queued for ASR" message
- Verify ASR service is running

**Q: No response from bot?**
- Check LLM service logs
- Verify TTS service is generating audio

**Q: Wrong audio format?**
- Verify μ-law ↔ PCM16 conversions
- Check sample rates (8000 Hz for Smartflo, 16000 Hz for processing)
