"""FastAPI application entry point"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import session_router

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


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "L and T Finance Customer Survey API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "POST /sessions": "Create a new survey session",
            "POST /sessions/{session_id}/answer": "Submit an answer",
            "GET /sessions/{session_id}/summary": "Get human-readable summary",
            "POST /sessions/{session_id}/confirm": "Confirm summary and get closing statement",
            "GET /sessions/{session_id}": "Get session information",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
