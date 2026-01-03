# Quick Start Guide

## Prerequisites
- Python 3.8+
- Node.js 14+ and npm
- Microphone access in browser

## 1. Create Environment File

Create `.env` file in the root directory with:

```
GEMINI_API_KEY=AIzaSyAXAbZupG0XawzVNmPk_7Qr16V6Yc713pA
ASR_API_URL=http://27.111.72.52:5073/transcribe
LOCAL_TTS_URL=http://27.111.72.52:5057/synthesize
DATABASE_URL=postgresql://neondb_owner:npg_6UP2GvZakNCw@ep-green-feather-a1ks02ct-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

## 2. Start Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Run backend
python run_backend.py
```

Backend will run on `http://localhost:8000`

## 3. Start Frontend

```bash
cd frontend
npm install
npm start
```

Frontend will open at `http://localhost:3000`

## 4. Use the System

1. Open `http://localhost:3000` in your browser
2. Browse and select a customer
3. Click "Start Call"
4. Allow microphone access when prompted
5. The bot will start asking questions in Hindi
6. Speak your responses naturally
7. View the summary when the call completes

## Troubleshooting

- **Import errors**: Make sure you're running from the correct directory
- **Database connection**: Verify DATABASE_URL in .env
- **Microphone not working**: Check browser permissions
- **API errors**: Verify ASR_API_URL and LOCAL_TTS_URL are accessible

