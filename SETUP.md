# Setup Instructions

## Environment Variables

Create a `.env` file in the root directory (`/Users/snehakiranmanded/LnT/.env`) with the following content:

```
GEMINI_API_KEY=AIzaSyAXAbZupG0XawzVNmPk_7Qr16V6Yc713pA
ASR_API_URL=http://27.111.72.52:5073/transcribe
LOCAL_TTS_URL=http://27.111.72.52:5057/synthesize
DATABASE_URL=postgresql://neondb_owner:npg_6UP2GvZakNCw@ep-green-feather-a1ks02ct-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

## Backend Setup

1. **Create a virtual environment (recommended):**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Run the backend server:**
```bash
# Option 1: Using the Python script
python run_backend.py

# Option 2: Direct uvicorn command
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The backend will be available at `http://localhost:8000`

## Frontend Setup

1. **Navigate to frontend directory:**
```bash
cd frontend
```

2. **Install dependencies:**
```bash
npm install
```

3. **Start the development server:**
```bash
npm start
```

The frontend will be available at `http://localhost:3000`

## Usage

1. Open the React app in your browser
2. Browse the list of customers from the database
3. Select a customer to start a call
4. Click "Start Call" to begin the voice conversation
5. The bot will ask 9 questions in Hindi
6. Speak your responses - they will be transcribed and analyzed
7. The conversation summary will be displayed when complete

## API Endpoints

- `GET /api/customers` - List all customers
- `GET /api/customers/{customer_id}` - Get customer details
- `POST /api/call/start/{customer_id}` - Start a call session
- `GET /api/call/{session_id}/summary` - Get call summary
- `WS /ws/call/{session_id}` - WebSocket for voice conversation

## Notes

- Ensure microphone permissions are granted in your browser
- The system uses WebRTC for audio capture (WebM format)
- Audio is sent to ASR API for transcription
- TTS API converts bot responses to speech
- Gemini AI analyzes customer responses for validation

