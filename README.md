# L&T Finance Voice Feedback System

A voice-to-voice feedback call system for L&T Finance customer feedback collection.

## Features

- Voice-to-voice conversation in Hindi
- 9 predefined feedback questions
- Real-time speech-to-text and text-to-speech
- Intelligent response tracking using Gemini AI
- Graceful exit handling
- Customer data management
- React web interface

## Setup

### Backend Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables (create `.env` file in root directory):
```
GEMINI_API_KEY=your_gemini_api_key
ASR_API_URL=http://27.111.72.52:5073/transcribe
LOCAL_TTS_URL=http://27.111.72.52:5057/synthesize
DATABASE_URL=your_database_url
```

3. Run the backend:
```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Or use the Python run script:
```bash
python run_backend.py
```

Or use the shell script:
```bash
chmod +x run_backend.sh
./run_backend.sh
```

### Frontend Setup

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Start the development server:
```bash
npm start
```

## API Endpoints

- `GET /api/customers` - Get list of customers
- `GET /api/customers/{customer_id}` - Get customer details
- `POST /api/call/start/{customer_id}` - Start a call session
- `GET /api/call/{session_id}/summary` - Get call summary
- `WS /ws/call/{session_id}` - WebSocket for voice conversation

## Project Structure

```
LnT/
├── backend/
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── models/
│   │   └── conversation.py
│   └── services/
│       ├── asr_service.py
│       ├── tts_service.py
│       ├── gemini_service.py
│       └── conversation_manager.py
├── frontend/
│   ├── src/
│   ├── public/
│   └── package.json
└── requirements.txt
```

