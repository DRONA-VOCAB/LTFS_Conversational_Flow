"""TTS Service using API"""

import time
import logging
import httpx
from typing import AsyncIterator
from config.settings import TTS_API_URL

logger = logging.getLogger(__name__)


# =====================================================================
#                         ★ STREAMING TTS ★
# =====================================================================
async def synthesize_stream(text: str) -> AsyncIterator[bytes]:
    """
    Stream TTS audio chunks from API

    Args:
        text: Text to synthesize

    Yields:
        PCM audio bytes (16-bit, mono, 24kHz)
    """
    try:
        if not text:
            logger.warning("Empty text provided")
            return

        logger.info(f"\n===== TTS STREAM START =====")
        logger.info(f"Input: {text}")
        logger.info("========================\n")

        # Make API call to TTS service
        # TTS_API_URL should be the base URL, endpoint is /synthesize
        # Handle case where URL might already include /synthesize
        base_url = TTS_API_URL.rstrip("/")
        if base_url.endswith("/synthesize"):
            base_url = base_url[:-11]  # Remove /synthesize
        tts_url = f"{base_url}/synthesize"
        logger.info(f"Calling TTS API: {tts_url}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", tts_url, json={"text": text}) as response:
                response.raise_for_status()

                chunk_count = 0
                last_t = time.time()

                async for chunk in response.aiter_bytes():
                    if chunk:
                        chunk_count += 1
                        now = time.time()
                        logger.debug(
                            f"TTS Chunk {chunk_count} | Δt={now-last_t:.3f}s | Size: {len(chunk)} bytes"
                        )
                        last_t = now
                        yield chunk

        logger.info(f"===== TTS STREAM END ({chunk_count} chunks) =====\n")
    except httpx.HTTPError as e:
        logger.error(f"TTS API HTTP Error: {e}")
        import traceback

        traceback.print_exc()
    except Exception as e:
        logger.error(f"TTS Error: {e}")
        import traceback

        traceback.print_exc()
