"""Main FastAPI application."""
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import init_db, close_db, get_db
from app.api.conversation import router as conversation_router
from app.middleware.error_handler import (
    validation_exception_handler,
    http_exception_handler,
    general_exception_handler
)
from app.middleware.logging_middleware import LoggingMiddleware
from app.utils.health_check import (
    check_database_health,
    check_asr_health,
    check_tts_health,
    check_llm_health
)
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    
    # Validate configuration
    if not settings.database_url:
        logger.error("DATABASE_URL is not configured!")
        raise ValueError("DATABASE_URL is required")
    
    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY is not configured - LLM features will not work")
    
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    await close_db()
    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Voice-to-voice conversational pipeline for L&T Finance feedback survey calls",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(conversation_router)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def root():
    """Root endpoint - redirects to web interface."""
    from fastapi.responses import FileResponse
    import os
    index_path = os.path.join("app", "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "status": "running",
        "web_interface": "/static/index.html"
    }


@app.get("/health")
async def health(request: Request, db: AsyncSession = Depends(get_db)):
    """Comprehensive health check endpoint."""
    health_status = {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "checks": {}
    }
    
    # Check database
    db_health = await check_database_health(db)
    health_status["checks"]["database"] = db_health
    if db_health["status"] != "healthy":
        health_status["status"] = "degraded"
    
    # Check ASR service
    asr_health = await check_asr_health()
    health_status["checks"]["asr"] = asr_health
    # Only mark as degraded if explicitly unhealthy (not unknown)
    if asr_health["status"] == "unhealthy":
        health_status["status"] = "degraded"
    
    # Check TTS service
    tts_health = await check_tts_health()
    health_status["checks"]["tts"] = tts_health
    # Only mark as degraded if explicitly unhealthy (not unknown)
    if tts_health["status"] == "unhealthy":
        health_status["status"] = "degraded"
    
    # Check LLM service
    llm_health = check_llm_health()
    health_status["checks"]["llm"] = llm_health
    if llm_health["status"] == "unhealthy":
        health_status["status"] = "degraded"
    
    return health_status

