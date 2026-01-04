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
GEMINI_MODEL=your-model-name
GEMINI_API_KEY=your-api-key
MAX_RETRIES=3
```

5. **Start the FastAPI server:**

```bash
python -m app.main
# OR
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The backend will be available at `http://localhost:8000`

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
VITE_API_URL=http://localhost:8000
```

(If not set, it defaults to `http://localhost:8000`)

4. **Start the development server:**

```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`
