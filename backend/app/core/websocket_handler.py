"""
WebSocket handler using core architecture (router, middleware, session_manager)
"""

import json
import asyncio
import logging
import time
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect

from core.router import router
from core.middleware import MiddlewarePipeline, MiddlewareContext
from core.session_manager import session_manager
from services.vad_silero import process_frame, cleanup_connection
from services.asr_service import transcribe_audio
from services.tts_service import synthesize_stream
from queues.asr_queue import asr_queue
from queues.tts_queue import tts_queue
from utils.latency_tracker import record_event, cleanup_tracking
from utils.session_data_storage import save_session_data
from sessions.session_store import get_session, save_session
from flow.flow_manager import (
    get_question_text,
    process_answer,
    get_summary_text,
    get_edit_prompt_text,
    get_closing_text,
)

logger = logging.getLogger(__name__)

# Track active connections
active_connections: Dict[str, WebSocket] = {}
connection_states: Dict[str, Dict] = {}

# Middleware pipeline
middleware_pipeline = MiddlewarePipeline()

USER_INPUT_TIMEOUT = 60  # 1 minute


async def get_websocket_id(websocket: WebSocket) -> str:
    """Get or create a unique ID for the WebSocket connection"""
    if not hasattr(websocket, "_id"):
        websocket._id = id(websocket)
    return str(websocket._id)


# Event handlers using router pattern
@router.route("init_session")
async def handle_init_session(event: dict, websocket: WebSocket, **kwargs):
    """Handle init_session event - for outbound calls, TTS speaks first"""
    websocket_id = kwargs.get("websocket_id")
    session_id = event.get("session_id")
    customer_name = event.get("customer_name")
    state = connection_states.get(websocket_id)

    logger.info(f"📞 Outbound call to: {customer_name} (session: {session_id})")

    if session_id and customer_name and state:
        state["session_id"] = session_id
        session = get_session(session_id)

        if session:
            await websocket.send_json(
                {
                    "type": "call_starting",
                    "message": f"Starting outbound call to {customer_name}",
                    "session_id": session_id,
                }
            )

            # Start directly with first question (no hardcoded greeting)
            question_text = get_question_text(session)
            save_session(session)
            if question_text:
                logger.info(f"📋 Sending first question: {question_text}")
                await send_tts(websocket_id, question_text)
        else:
            error_msg = f"Session not found: {session_id}"
            logger.error(f"❌ {error_msg}")
            await websocket.send_json({"type": "error", "message": error_msg})
    else:
        error_msg = f"Invalid init_session params"
        logger.error(f"❌ {error_msg}")
        await websocket.send_json({"type": "error", "message": error_msg})


@router.route("tts_finished")
async def handle_tts_finished(event: dict, websocket: WebSocket, **kwargs):
    """Handle tts_finished event"""
    websocket_id = kwargs.get("websocket_id")
    state = connection_states.get(websocket_id)

    if state:
        state["tts_playing"] = False

        # Check if we need to end the call
        if state.get("pending_end"):
            state["pending_end"] = False
            state["mic_enabled"] = False
            logger.info("✅ Survey completed, call ended")
            await websocket.send_json(
                {"type": "survey_completed", "message": "Survey completed successfully"}
            )
            return

        # Enable mic after TTS finishes
        state["mic_enabled"] = True
        logger.info(f"🎤 Mic enabled for {websocket_id}")

        await websocket.send_json(
            {"type": "mic_enabled", "message": "Microphone is now active"}
        )
    else:
        logger.error(f"❌ No state found for websocket_id: {websocket_id}")


@router.route("tts_started")
async def handle_tts_started(event: dict, websocket: WebSocket, **kwargs):
    """Handle tts_started event"""
    websocket_id = kwargs.get("websocket_id")
    state = connection_states.get(websocket_id)
    if state:
        state["mic_enabled"] = False
        state["tts_playing"] = True
        logger.info(f"🔇 Mic disabled for {websocket_id} (TTS playing)")


@router.route("tts_request")
async def handle_tts_request(event: dict, websocket: WebSocket, **kwargs):
    """Handle tts_request event"""
    websocket_id = kwargs.get("websocket_id")
    text = event.get("text")
    if text:
        await send_tts(websocket_id, text)


@router.route("ping")
async def handle_ping(event: dict, websocket: WebSocket, **kwargs):
    """Handle ping event"""
    await websocket.send_json({"type": "pong"})


async def send_tts(websocket_id: str, text: str):
    """Send text to TTS queue for synthesis"""
    websocket = active_connections.get(websocket_id)
    if websocket:
        await tts_queue.put((websocket, text, None))
    else:
        logger.error(f"❌ WebSocket not found: {websocket_id}")


async def process_asr_queue(websocket_id: str):
    """Process ASR queue items"""
    while websocket_id in active_connections:
        try:
            try:
                item = await asyncio.wait_for(asr_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            websocket, audio_bytes, utterance_id = item

            if websocket != active_connections.get(websocket_id):
                await asr_queue.put(item)
                continue

            state = connection_states.get(websocket_id)
            if not state:
                continue

            state["processing_asr"] = True
            state["mic_enabled"] = False

            logger.info(f"🔍 ASR: Processing audio for {websocket_id}")

            asr_result = await transcribe_audio(audio_bytes)
            transcription = asr_result.get("transcription", "").strip()

            # Log ASR transcript
            logger.info(f"📝 ASR Transcript: '{transcription}'")

            if utterance_id:
                record_event(utterance_id, "ASR_COMPLETE")

            if transcription:
                state["last_user_input_time"] = time.time()
                logger.info(f"⏰ Updated last_user_input_time for {websocket_id}")

                if not state.get("session_id"):
                    # Create session with name
                    logger.info(f"Creating session with name: {transcription}")
                    try:
                        from sessions.session_schema import create_session
                        from sessions.session_store import (
                            save_session as save_session_store,
                        )
                        import uuid
                        from datetime import datetime

                        session_id = f"session_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"
                        session = create_session(session_id, transcription.strip())
                        save_session_store(session)
                        state["session_id"] = session_id

                        websocket = active_connections.get(websocket_id)
                        if websocket:
                            await websocket.send_json(
                                {
                                    "type": "session_created",
                                    "session_id": session_id,
                                    "customer_name": transcription.strip(),
                                }
                            )

                        question_text = get_question_text(session)
                        save_session_store(session)

                        if question_text:
                            await send_tts(websocket_id, question_text)
                    except Exception as e:
                        logger.error(f"Error creating session: {e}")
                    continue

                # Process answer
                session_id = state["session_id"]
                session = get_session(session_id)

                if session:
                    logger.info(
                        f"📥 Processing answer: '{transcription}' for phase={session.get('phase', 'questions')}, question={session.get('current_question')}"
                    )
                    result = process_answer(session, transcription)
                    logger.info(f"📤 Answer result: {result}")
                    save_session(session)

                    if result == "SUMMARY":
                        # All questions done, read summary (confirmation is embedded)
                        logger.info("📝 Generating and reading summary...")
                        summary_text = get_summary_text(session)
                        save_session(session)
                        await send_tts(websocket_id, summary_text)
                        # Mic will be enabled after TTS, user responds to confirmation

                    elif result == "CLOSING":
                        # Check if there's an acknowledgment text (e.g., edit confirmation) to speak first
                        ack_text = session.get("acknowledgment_text")
                        if ack_text:
                            logger.info(f"💬 Speaking acknowledgment: {ack_text}")
                            await send_tts(websocket_id, ack_text)
                            # Clear it so closing message can be spoken
                            session.pop("acknowledgment_text", None)
                            save_session(session)

                        # Say closing statement and end
                        logger.info("👋 Saying closing statement...")
                        closing_text = get_closing_text(session)
                        save_session(session)
                        save_session_data(session_id, session)
                        await send_tts(websocket_id, closing_text)
                        state["pending_end"] = True
                        state["timeout_monitoring"] = False

                    elif result == "ASK_EDIT":
                        # User said no to confirmation, ask what to edit
                        logger.info("✏️ User wants to edit, asking which field...")
                        await send_tts(websocket_id, get_edit_prompt_text())

                    elif result == "REPEAT_EDIT":
                        # Could not detect which field, ask again
                        logger.info("🔄 Could not detect field, asking again...")
                        await send_tts(
                            websocket_id,
                            "माफ़ कीजिए, मुझे समझ नहीं आया। कृपया बताइए कौन सी जानकारी बदलनी है?",
                        )

                    elif result == "REPEAT_SUMMARY":
                        # Unclear confirmation, repeat summary
                        logger.info("🔄 Unclear confirmation, repeating summary...")
                        summary_text = session.get(
                            "generated_summary"
                        ) or get_summary_text(session)
                        await send_tts(websocket_id, summary_text)

                    elif result == "END":
                        # Max retries exceeded, say closing and end
                        logger.info("❌ Max retries exceeded, saying closing...")
                        closing_text = get_closing_text(session)
                        save_session(session)
                        save_session_data(session_id, session)
                        await send_tts(websocket_id, closing_text)
                        state["pending_end"] = True
                        state["timeout_monitoring"] = False

                    elif result in ["NEXT", "REPEAT"]:
                        question_text = get_question_text(session)
                        save_session(session)
                        logger.info(
                            f"📋 Next question: {question_text[:50] if question_text else 'None'}..."
                        )

                        if question_text:
                            await send_tts(websocket_id, question_text)
                        else:
                            # No more questions, move to summary
                            logger.info("📝 No more questions, generating summary...")
                            session["phase"] = "summary"
                            summary_text = get_summary_text(session)
                            save_session(session)
                            await send_tts(websocket_id, summary_text)
                            state["pending_confirmation"] = True
                    else:
                        logger.warning(
                            f"⚠️ Unknown result from process_answer: {result}"
                        )

            if not state.get("tts_playing"):
                state["mic_enabled"] = True
            state["processing_asr"] = False

            websocket = active_connections.get(websocket_id)
            if websocket and transcription:
                await websocket.send_json(
                    {
                        "type": "transcription",
                        "text": transcription,
                        "detected_language": asr_result.get("detected_language"),
                        "language_confidence": asr_result.get("language_confidence"),
                    }
                )

            if utterance_id:
                cleanup_tracking(utterance_id)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error processing ASR: {e}")
            state = connection_states.get(websocket_id)
            if state:
                state["processing_asr"] = False
                if not state.get("tts_playing"):
                    state["mic_enabled"] = True


async def process_tts_queue(websocket_id: str):
    """Process TTS queue items"""
    while websocket_id in active_connections:
        try:
            try:
                item = await asyncio.wait_for(tts_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            websocket, text, utterance_id = item

            if websocket != active_connections.get(websocket_id):
                await tts_queue.put(item)
                continue

            websocket = active_connections.get(websocket_id)
            if not websocket:
                continue

            state = connection_states.get(websocket_id)
            if state:
                state["tts_playing"] = True
                state["mic_enabled"] = False

            logger.info(f"🗣️ TTS playing: {text[:50]}...")
            # Send bot_message so frontend can display the question
            await websocket.send_json({"type": "bot_message", "text": text})
            await websocket.send_json({"type": "tts_start", "text": text})

            chunk_count = 0
            async for audio_chunk in synthesize_stream(text):
                await websocket.send_bytes(audio_chunk)
                chunk_count += 1

            await websocket.send_json({"type": "tts_end", "chunks_sent": chunk_count})
            logger.info(f"✅ TTS complete: {chunk_count} chunks sent")

            if state:
                state["tts_playing"] = False
                if not state.get("processing_asr"):
                    state["last_user_input_time"] = time.time()
                    logger.info(f"⏰ Reset last_user_input_time after TTS for {websocket_id}")

            if utterance_id:
                record_event(utterance_id, "TTS_COMPLETE")
                cleanup_tracking(utterance_id)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error processing TTS: {e}")
            state = connection_states.get(websocket_id)
            if state:
                state["tts_playing"] = False
                if not state.get("processing_asr"):
                    state["mic_enabled"] = True

async def monitor_timeout(websocket_id: str):
    """Monitor for user input timeout and trigger closing if timeout occurs"""
    state = connection_states.get(websocket_id)
    if not state:
        return
    
    while websocket_id in active_connections and state.get("timeout_monitoring", True):
        try:
            await asyncio.sleep(5)  # Check every 5 seconds
            
            if websocket_id not in active_connections:
                break
                
            state = connection_states.get(websocket_id)
            if not state or not state.get("timeout_monitoring", True):
                break
            
            # Only monitor if we have a session and mic is enabled (waiting for user input)
            if state.get("session_id") and state.get("mic_enabled") and not state.get("tts_playing"):
                last_input_time = state.get("last_user_input_time")
                if last_input_time:
                    elapsed = time.time() - last_input_time
                    if elapsed >= USER_INPUT_TIMEOUT:
                        logger.warning(f"⏰ Timeout: No user input for {elapsed:.1f} seconds, closing call for {websocket_id}")
                        
                        # Disable timeout monitoring and mic
                        state["timeout_monitoring"] = False
                        state["mic_enabled"] = False
                        
                        # Get session and trigger closing
                        session_id = state.get("session_id")
                        if session_id:
                            session = get_session(session_id)
                            if session:
                                # Set phase to closing
                                session["phase"] = "closing"
                                session["call_should_end"] = True
                                save_session(session)
                                
                                # Get closing statement (this is what will be spoken)
                                closing_text = get_closing_text(session)
                                save_session(session)
                                save_session_data(session_id, session)
                                
                                websocket = active_connections.get(websocket_id)
                                if websocket:
                                    # Send closing statement via TTS
                                    await send_tts(websocket_id, closing_text)
                                    # Set pending_end so websocket closes after TTS finishes
                                    state["pending_end"] = True
                                    logger.info(f"📢 Playing closing statement due to timeout: {closing_text[:50]}...")
                                    
                        break
                        
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in timeout monitor for {websocket_id}: {e}")

            
async def websocket_audio_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint using core architecture"""
    logger.info("🔌 WebSocket connection attempt received")
    await websocket.accept()
    logger.info("✅ WebSocket accepted")

    websocket_id = await get_websocket_id(websocket)
    active_connections[websocket_id] = websocket
    logger.info(f"📝 WebSocket ID assigned: {websocket_id}")

    connection_states[websocket_id] = {
        "mic_enabled": False,
        "session_id": None,
        "tts_playing": False,
        "processing_asr": False,
        "pending_question": False,  # For outbound calls - flag to send first question after greeting
        "last_user_input_time": None,  # Track last time user provided input
        "timeout_monitoring": True,  # Enable timeout monitoring
    }
    logger.info(f"📊 Connection state initialized for {websocket_id}")

    logger.info(f"✅ WebSocket connected: {websocket_id}")

    try:
        logger.info(f"🚀 Starting background tasks for {websocket_id}")
        asr_processor_task = asyncio.create_task(process_asr_queue(websocket_id))
        tts_processor_task = asyncio.create_task(process_tts_queue(websocket_id))
        timeout_monitor_task = asyncio.create_task(monitor_timeout(websocket_id))
        logger.info(f"✅ Background tasks started for {websocket_id}")

        # Send ready message to client
        await websocket.send_json(
            {
                "type": "websocket_ready",
                "message": "WebSocket ready, waiting for init_session",
            }
        )
        logger.info(f"📤 Sent websocket_ready message to client")

        while True:
            try:
                message = await websocket.receive()

                if "text" in message:
                    logger.info(f"📝 Text message: {message['text'][:100]}...")
                    # Process through middleware
                    ctx = await middleware_pipeline.process(message["text"])

                    if ctx.error:
                        logger.error(f"❌ Middleware error: {ctx.error}")
                        continue

                    if ctx.json_data:
                        # Get event type from data
                        event_type = ctx.json_data.get("type")

                        if event_type:
                            if router.get_handler(event_type):
                                try:
                                    # Dispatch to handler
                                    await router.dispatch(
                                        ctx.json_data,
                                        websocket,
                                        websocket_id=websocket_id,
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"❌ Error in handler {event_type}: {e}",
                                        exc_info=True,
                                    )
                                    await websocket.send_json(
                                        {
                                            "type": "error",
                                            "message": f"Handler error: {str(e)}",
                                        }
                                    )
                            else:
                                logger.warning(
                                    f"⚠️ No handler for event type: {event_type}"
                                )
                                await websocket.send_json(
                                    {
                                        "type": "error",
                                        "message": f"No handler for event type: {event_type}",
                                    }
                                )
                        else:
                            logger.warning(
                                f"⚠️ No event type in message: {ctx.json_data}"
                            )
                            await websocket.send_json(
                                {
                                    "type": "error",
                                    "message": "Missing 'type' field in message",
                                }
                            )

                elif "bytes" in message:
                    # Handle binary audio frames (no logging - too verbose)
                    audio_frame = message["bytes"]
                    state = connection_states[websocket_id]

                    if state["mic_enabled"] and not state["processing_asr"]:
                        await process_frame(
                            websocket, audio_frame, stream_sid=websocket_id
                        )

            except WebSocketDisconnect:
                logger.info(f"❌ WebSocket disconnected: {websocket_id}")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}")
                import traceback

                traceback.print_exc()
                break

    finally:
        cleanup_connection(websocket)
        if websocket_id in active_connections:
            del active_connections[websocket_id]
        if websocket_id in connection_states:
            del connection_states[websocket_id]

        asr_processor_task.cancel()
        tts_processor_task.cancel()
        timeout_monitor_task.cancel()

        try:
            await asr_processor_task
        except asyncio.CancelledError:
            pass
        try:
            await tts_processor_task
        except asyncio.CancelledError:
            pass
        try:
            await timeout_monitor_task
        except asyncio.CancelledError:
            pass
