"""
LLM Service - Handles communication with external chatbot API
Combines API calls and queue processing
"""

import asyncio
import logging
from typing import Dict, Any, Optional

import httpx

from config.settings import CHATBOT_API_URL
from queues.llm_queue import llm_queue
from queues.tts_queue import tts_queue
from utils.latency_tracker import record_event

logger = logging.getLogger(__name__)

# Timeout for API calls (in seconds)
API_TIMEOUT = 30.0


async def call_chatbot_init(customer_name: str) -> Dict[str, Any]:
    """Initialize chatbot session"""
    try:
        logger.info(f"Initializing chatbot for customer: {customer_name}")
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(
                f"{CHATBOT_API_URL}/chat/init",
                json={"customer_name": customer_name}
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Chatbot initialized - Session: {result.get('session_id')}")
            return result
    except Exception as e:
        logger.error(f"Error calling chatbot init API: {e}", exc_info=True)
        raise


async def call_chatbot_message(session_id: str, user_input: str) -> Dict[str, Any]:
    """Send message to chatbot API"""
    fallback = {"bot_response": "कृपया दोबारा बताइए।", "next_action": "continue", "extracted_data": {}}
    try:
        logger.info(f"Chatbot message - Session: {session_id}, Input: {user_input}")
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(
                f"{CHATBOT_API_URL}/chat/{session_id}",
                json={"user_input": user_input}
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Bot: {result.get('bot_response', '')[:50]}... | Action: {result.get('next_action', '')}")
            return result
    except Exception as e:
        logger.error(f"Chatbot API error: {e}", exc_info=True)
        return fallback


async def get_chatbot_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session data from chatbot API"""
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.get(f"{CHATBOT_API_URL}/chat/{session_id}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json().get("session", {})
    except Exception as e:
        logger.error(f"Error getting chatbot session: {e}", exc_info=True)
        return None


async def llm_service_consumer(websocket_id: str, active_connections: Dict, connection_states: Dict):
    """Process LLM queue - send transcription to chatbot API and get response"""
    logger.info(f"LLM consumer started for {websocket_id}")
    while websocket_id in active_connections:
        try:
            try:
                item = await asyncio.wait_for(llm_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            websocket, transcription, utterance_id = item

            # Check if this is for our connection
            if websocket != active_connections.get(websocket_id):
                await llm_queue.put(item)
                continue

            state = connection_states.get(websocket_id)
            if not state:
                continue

            chatbot_session_id = state.get("chatbot_session_id")
            if not chatbot_session_id:
                logger.warning("No chatbot_session_id found in state")
                continue

            logger.info(f"🤖 LLM: Processing for session {chatbot_session_id}")

            # Call chatbot API
            result = await call_chatbot_message(chatbot_session_id, transcription)
            bot_response = result.get("bot_response", "")
            next_action = result.get("next_action", "continue")

            # Update state with extracted data
            extracted_data = result.get("extracted_data", {})
            for key, value in extracted_data.items():
                if value is not None and value != "null":
                    state[key] = value

            # Send bot response to TTS queue
            if bot_response:
                turn_id = state.get("current_turn_id")
                await tts_queue.put((websocket, bot_response, utterance_id, turn_id))

            # Handle end_call action
            if next_action == "end_call":
                state["pending_end"] = True
                logger.info("🔚 Call will end after TTS finishes")

            if utterance_id:
                record_event(utterance_id, "LLM_COMPLETE")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error processing LLM: {e}", exc_info=True)

    logger.info(f"LLM consumer stopped for {websocket_id}")
