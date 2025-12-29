"""Health check utilities."""
import httpx
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.config import settings
import logging

logger = logging.getLogger("lnt_finance_feedback")


async def check_database_health(db: AsyncSession) -> Dict[str, Any]:
    """Check database connectivity."""
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        return {"status": "healthy", "message": "Database connection OK"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "message": f"Database error: {str(e)}"}


async def check_asr_health() -> Dict[str, Any]:
    """Check ASR service health."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try health endpoint first
            health_url = settings.asr_url.replace("/transcribe", "/health")
            response = await client.get(health_url)
            if response.status_code == 200:
                return {"status": "healthy", "message": "ASR service OK"}
            elif response.status_code == 404:
                # Health endpoint doesn't exist, but service might be running
                # Try to ping the actual service endpoint
                try:
                    ping_response = await client.get(settings.asr_url, timeout=2.0)
                    return {"status": "healthy", "message": "ASR service reachable (no health endpoint)"}
                except:
                    return {"status": "unknown", "message": "ASR service health endpoint not available"}
            else:
                return {"status": "unhealthy", "message": f"ASR returned {response.status_code}"}
    except httpx.TimeoutException:
        return {"status": "unknown", "message": "ASR service timeout - may be unavailable"}
    except Exception as e:
        logger.warning(f"ASR health check failed: {e}")
        return {"status": "unknown", "message": f"ASR check failed: {str(e)}"}


async def check_tts_health() -> Dict[str, Any]:
    """Check TTS service health."""
    try:
        # Use same timeout configuration as TTS service (10s connect, 5s read)
        timeout = httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Try health endpoint first
            health_url = settings.tts_url.replace("/synthesize", "/health")
            try:
                response = await client.get(health_url)
                if response.status_code == 200:
                    return {"status": "healthy", "message": "TTS service OK"}
                elif response.status_code == 404:
                    # Health endpoint doesn't exist, but service might be running
                    # Try to ping the actual service endpoint
                    try:
                        ping_response = await client.get(settings.tts_url, timeout=2.0)
                        return {"status": "healthy", "message": "TTS service reachable (no health endpoint)"}
                    except httpx.TimeoutException:
                        return {"status": "unknown", "message": f"TTS service at {settings.tts_url} is reachable but no health endpoint and ping timed out."}
                    except httpx.ConnectError as e:
                        return {"status": "unhealthy", "message": f"TTS service at {settings.tts_url} is unreachable (no health endpoint): {str(e)}"}
                else:
                    return {"status": "unhealthy", "message": f"TTS service at {settings.tts_url} returned {response.status_code}"}
            except httpx.ConnectTimeout:
                return {"status": "unhealthy", "message": f"TTS service at {settings.tts_url} connection timed out."}
            except httpx.TimeoutException:
                return {"status": "unknown", "message": f"TTS service at {settings.tts_url} request timed out - may be unavailable."}
    except httpx.ConnectTimeout:
        return {"status": "unhealthy", "message": f"TTS service at {settings.tts_url} connection timed out."}
    except httpx.TimeoutException:
        return {"status": "unknown", "message": f"TTS service at {settings.tts_url} request timed out - may be unavailable."}
    except Exception as e:
        logger.warning(f"TTS health check failed for {settings.tts_url}: {e}")
        return {"status": "unknown", "message": f"TTS check failed for {settings.tts_url}: {str(e)}"}


def check_llm_health() -> Dict[str, Any]:
    """Check LLM service health (Gemini API key)."""
    if settings.gemini_api_key:
        return {"status": "healthy", "message": "Gemini API key configured"}
    else:
        return {"status": "unhealthy", "message": "Gemini API key not configured"}

