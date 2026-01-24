# Feedback Call System

This project implements an automated feedback calling system that collects customer responses through an intelligent voice flow. It handles outbound call initiation, dynamic question logic, response validation, and structured data capture.It ensures consistent customer interactions while reducing manual effort.

# Core Components

- Voice Platform – call initiation, IVR/telephony
- ASR (Speech-to-Text) – converts audio to text
- Hybrid AI Brain – intent classifier + LLM for natural responses
- Orchestration Engine – manages the full feedback workflow
- Business Logic Layer – validation, summary creation, correction handling
- Data Layer – Excel/DB updates with full or partial feedback
- TTS (Text-to-Speech) – responds in customer's detected language

# Folder Structure

```
project-root/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── conversation.py
│   ├── schema/
│   │   ├── __init__.py
│   │   ├── feedback_request.py
│   │   ├── feedback_response.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── outbound_call_service.py
│   │   ├── feedback_flow_manager.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── validators.py
│   │   ├── formatter.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── call_event.py
│   │   ├── feedback_responses.py
│
├── requirements.txt
└── README.md
```

# Setup Guide - L&T Finance Customer Survey

## Backend Setup (FastAPI)

1. **Navigate to the project root:**

```bash
cd E:\Vocab.ai\LTFs\LTFS_TXT
```

2. **Activate virtual environment:**

```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. **Install dependencies (if not already installed):**

```bash
pip install -r requirements.txt
```

4. **Set up environment variables:**
   Create a `.env` file in the project root:

```
GPT_OSS_MODEL=openai/gpt-oss-20b
GPT_OSS_API_KEY=local
GPT_OSS_API_BASE=http://192.168.30.132:8001/v1
MAX_RETRIES=3
```

5. **Start the FastAPI server:**

```bash
python -m app.main
# OR
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

The backend will be available at `http://localhost:8001`

## Frontend Setup (React + Tailwind)

1. **Navigate to the frontend directory:**

```bash
cd frontend
```

2. **Install dependencies:**

```bash
npm install
```

3. **Configure API URL (optional):**
   Create a `.env` file in the `frontend` directory:

```
VITE_API_URL=http://localhost:8001
```

(If not set, it defaults to `http://localhost:8001`)

4. **Start the development server:**

```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`
