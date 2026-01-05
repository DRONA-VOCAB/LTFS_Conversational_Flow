# L&T Finance Customer Survey - Frontend

React frontend for the L&T Finance Customer Survey chatbot.

## Setup

1. Create a `.env` file in the root directory

```bash
    GEMINI_MODEL=""
    GEMINI_API_KEY=""
    MAX_RETRIES=2
    DATABASE_URL=""
    ASR_API_URL=http://27.111.72.52:5073/transcribe
    TTS_API_URL=http://27.111.72.52:5057/synthesize
    VITE_API_URL=http://27.111.72.55:8001
```

2. Frontend:

```bash
    cd frontend
    npm install
    npm run dev
```

3. Backend:

```bash
    cd backend
    pip install -r requirements.txt
    cd app
    uvicorn main:app --reload
```
