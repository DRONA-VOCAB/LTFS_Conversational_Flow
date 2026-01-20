from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from core.websocket_handler import websocket_audio_endpoint
from routes import session_router

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

# routers
app.include_router(session_router)
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

    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
