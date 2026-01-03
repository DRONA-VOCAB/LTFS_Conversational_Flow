# L&T Finance Voice Feedback System - Project Summary

## Overview
A complete voice-to-voice feedback call system for L&T Finance that conducts automated customer feedback calls in Hindi using AI-powered conversation management.

## Architecture

### Backend (FastAPI)
- **Framework**: FastAPI with WebSocket support
- **Database**: PostgreSQL (NeonDB) with SQLAlchemy ORM
- **AI Integration**: Google Gemini Pro for response analysis
- **External Services**:
  - ASR (Speech-to-Text): Whisper medium fine-tuned API
  - TTS (Text-to-Speech): ChatterBox API

### Frontend (React)
- **Framework**: React 18
- **Audio Handling**: WebRTC MediaRecorder API
- **Communication**: WebSocket for real-time bidirectional communication

## Key Features

1. **9 Predefined Hindi Questions**
   - Customer verification
   - Loan confirmation
   - Payment verification
   - Payment details (who, when, how, why, amount)
   - Closing message

2. **Intelligent Response Tracking**
   - Valid answer detection
   - Off-topic detection
   - Customer interest level monitoring
   - Busy/unavailable detection
   - Clarification requests
   - Graceful exit handling

3. **Conversation Management**
   - Automatic question progression
   - Response validation using Gemini AI
   - Retry logic (max 3 attempts per question)
   - Graceful termination after non-responsive behavior

4. **Data Tracking**
   - Complete conversation JSON summary
   - Response status tracking
   - Confidence scoring
   - Timestamp recording
   - Attempt counting

## Project Structure

```
LnT/
├── backend/
│   ├── config.py              # Configuration & settings
│   ├── database.py            # Database models & connection
│   ├── main.py                # FastAPI application & routes
│   ├── models/
│   │   └── conversation.py    # Conversation data models
│   └── services/
│       ├── asr_service.py     # Speech-to-text service
│       ├── tts_service.py     # Text-to-speech service
│       ├── gemini_service.py  # Gemini AI integration
│       └── conversation_manager.py  # Conversation flow logic
├── frontend/
│   ├── src/
│   │   ├── App.js             # Main application
│   │   ├── components/
│   │   │   ├── CustomerList.js    # Customer selection UI
│   │   │   └── CallInterface.js   # Call interface & WebSocket
│   │   └── ...
│   └── package.json
├── requirements.txt           # Python dependencies
├── .env                       # Environment variables (create manually)
├── README.md                  # Project documentation
├── SETUP.md                   # Setup instructions
└── run_backend.py            # Backend startup script
```

## API Flow

1. **Customer Selection**
   - Frontend fetches customers from `/api/customers`
   - User selects a customer
   - Frontend calls `/api/call/start/{customer_id}`
   - Backend creates conversation session and returns session_id

2. **Voice Conversation**
   - Frontend establishes WebSocket connection to `/ws/call/{session_id}`
   - Backend sends first question as audio + JSON
   - Frontend records user audio (WebM format)
   - Audio sent to backend via WebSocket
   - Backend sends audio to ASR API for transcription
   - Transcribed text analyzed by Gemini AI
   - Backend generates appropriate response
   - Response converted to speech via TTS API
   - Audio sent back to frontend for playback
   - Process repeats until all questions answered or call terminated

3. **Call Completion**
   - Summary JSON generated with all responses
   - Summary sent to frontend
   - Call ends gracefully

## Gemini AI System Prompts

The system uses sophisticated prompts to analyze customer responses:
- Determines if answer is valid
- Detects off-topic responses
- Identifies disinterest or busy status
- Requests clarification when needed
- Provides appropriate Hindi responses

## Response Status Types

- `valid_answer`: Customer provided appropriate response
- `off_topic`: Customer went off-topic
- `not_interested`: Customer shows disinterest
- `busy`: Customer is busy/unavailable
- `clarification_needed`: Response unclear, needs clarification
- `no_response`: No response detected

## Configuration

All configuration is done via environment variables in `.env`:
- `GEMINI_API_KEY`: Google Gemini API key
- `ASR_API_URL`: Speech-to-text API endpoint
- `LOCAL_TTS_URL`: Text-to-speech API endpoint
- `DATABASE_URL`: PostgreSQL connection string

## Error Handling

- Graceful degradation on API failures
- Retry logic for failed transcriptions
- Fallback responses for unclear inputs
- Connection error handling
- Automatic cleanup on disconnect

## Security Considerations

- Environment variables for sensitive data
- CORS configuration (adjust for production)
- WebSocket connection validation
- Session management

## Future Enhancements

- Persistent storage of conversation summaries
- Analytics dashboard
- Call recording storage
- Multi-language support
- Scheduled call automation
- Integration with CRM systems

