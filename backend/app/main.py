from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from core.websocket_handler import websocket_audio_endpoint
from routes import customer_router, sessions_router

app = FastAPI(
    title="L and T Finance Customer Survey API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include customer routes (both /customers and /sessions/customers)
app.include_router(customer_router)
app.include_router(sessions_router)

# Main WebSocket endpoint
app.websocket("/ws/audio")(websocket_audio_endpoint)

# -------- PATHS (ABSOLUTE) --------
BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
STATIC_DIR = BASE_DIR / "app/static"
AUDIO_DIR = BASE_DIR / "audio_files"
ASR_AUDIO_DIR = AUDIO_DIR / "asr_audios"
TTS_AUDIO_DIR = AUDIO_DIR / "tts_audios"

print("BASE_DIR =", BASE_DIR)
print("ASR exists =", ASR_AUDIO_DIR.exists())
print("TTS exists =", TTS_AUDIO_DIR.exists())

# -------- STATIC MOUNTS --------
app.mount("/asr_audios", StaticFiles(directory=ASR_AUDIO_DIR), name="asr_audios")
app.mount("/tts_audios", StaticFiles(directory=TTS_AUDIO_DIR), name="tts_audios")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    from config.settings import HOST, PORT

    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
