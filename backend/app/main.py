"""FastAPI application entry point"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import session_router
from core.websocket_handler import websocket_audio_endpoint

# Create FastAPI app
app = FastAPI(
    title="L and T Finance Customer Survey API",
    description="API for managing customer survey sessions",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(session_router)

# WebSocket endpoint
app.websocket("/ws/audio")(websocket_audio_endpoint)


from fastapi.staticfiles import StaticFiles
app.mount(
    "/", 
    StaticFiles(directory="static", html=True),
    name="frontend"
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
