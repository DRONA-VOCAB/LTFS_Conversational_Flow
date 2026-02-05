"""
WebSocket handler using core architecture (router, middleware, session_manager)
"""

import json
import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect

from core.router import router
from core.middleware import MiddlewarePipeline, MiddlewareContext
from core.session_manager import session_manager
from services.vad_silero import process_frame, cleanup_connection
from config.settings import PUBLIC_BASE_URL
from services.asr_service import pcm16_to_wav, transcribe_audio
from services.tts_service import synthesize_stream
from services.google_sheet_logger import log_interaction
from queues.asr_queue import asr_queue
from queues.tts_queue import tts_queue
from utils.latency_tracker import record_event, cleanup_tracking
from utils.session_data_storage import save_session_data
from utils.filler_manager import get_filler
from sessions.session_store import get_session, save_session
from flow.flow_manager import (
    get_question_text,
    process_answer,
    get_summary_text,
    get_closing_text,
)

logger = logging.getLogger(__name__)

# Track active connections
active_connections: Dict[str, WebSocket] = {}
connection_states: Dict[str, Dict] = {}

# Middleware pipeline
middleware_pipeline = MiddlewarePipeline()

USER_INPUT_TIMEOUT = 60  # 1 minute
AUDIO_ROOT = Path(__file__).resolve().parents[2] / "audio_files"
ASR_AUDIO_DIR = AUDIO_ROOT / "asr_audios"
TTS_AUDIO_DIR = AUDIO_ROOT / "tts_audios"
ASR_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
TTS_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_session_id(session_id: str) -> str:
    return (session_id or "session").replace(" ", "_")


def _next_turn_base(state: Dict, session_id: str) -> str:
    counter = state.get("turn_counter", 0) + 1
    state["turn_counter"] = counter
    return f"{_sanitize_session_id(session_id)}_turn{counter:03d}"


def _prepare_audio_bytes(raw_bytes: bytes) -> bytes:
    """Ensure bytes are WAV formatted."""
    if raw_bytes[:4] == b"RIFF":
        return raw_bytes
    return pcm16_to_wav(raw_bytes)


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _build_audio_url(folder: str, filename: str) -> str:
    base = PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/{folder}/{filename}"


def _save_audio_non_blocking(path: Path, data: bytes) -> None:
    asyncio.create_task(asyncio.to_thread(_write_bytes, path, data))


async def _log_interaction_if_ready(
    websocket_id: str, llm_response: str, tts_audio_url: Optional[str]
) -> None:
    """Send interaction details to Google Sheets without blocking the pipeline."""
    state = connection_states.get(websocket_id)
    if not state:
        return

    asr_url = state.get("last_asr_audio_url")
    transcription = state.get("last_transcription")
    base_name = state.get("current_turn_base")

    if not (asr_url and transcription and tts_audio_url):
        return

    if base_name and state.get("last_logged_base") == base_name:
        return

    session_id = state.get("session_id") or f"ws_{websocket_id}"

    payload = {
        "session_id": session_id,
        "asr_audio_url": asr_url,
        "transcription": transcription,
        "llm_response": llm_response,
        "tts_audio_url": tts_audio_url,
    }

    if base_name:
        state["last_logged_base"] = base_name

    asyncio.create_task(log_interaction(payload))


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


async def send_tts(websocket_id: str, text: str, audio_base: Optional[str] = None):
    """Send text to TTS queue for synthesis and downstream logging."""
    websocket = active_connections.get(websocket_id)
    state = connection_states.get(websocket_id, {})

    if websocket:
        session_id = state.get("session_id") or websocket_id
        base_name = audio_base or state.get("current_turn_base") or _next_turn_base(
            state, session_id
        )
        state["current_turn_base"] = base_name
        await tts_queue.put((websocket, text, None, base_name))
    else:
        logger.error(f"❌ WebSocket not found: {websocket_id}")


async def send_tts_and_wait(websocket_id: str, text: str, audio_base: Optional[str] = None):
    """
    Send TTS and wait for it to complete playing.
    Returns when TTS finishes playing.
    """
    websocket = active_connections.get(websocket_id)
    state = connection_states.get(websocket_id, {})
    
    if not websocket:
        logger.error(f"❌ WebSocket not found: {websocket_id}")
        return
    
    # Create an event to track when TTS finishes
    tts_finished_event = asyncio.Event()
    
    # Store callback to set event when TTS finishes
    def on_tts_finished():
        if state.get("_tts_finished_callback") == on_tts_finished:
            state["_tts_finished_callback"] = None
            tts_finished_event.set()
    
    state["_tts_finished_callback"] = on_tts_finished
    
    # Send TTS
    await send_tts(websocket_id, text, audio_base)
    
    # Wait for TTS to finish (with timeout)
    try:
        await asyncio.wait_for(tts_finished_event.wait(), timeout=30.0)
    except asyncio.TimeoutError:
        logger.warning(f"⚠️ TTS wait timeout for: {text[:50]}...")
        # Clear callback on timeout
        if state.get("_tts_finished_callback") == on_tts_finished:
            state["_tts_finished_callback"] = None


async def process_with_filler(
    websocket_id: str,
    session: Dict,
    transcription: str,
    response_audio_base: Optional[str] = None,
):
    """
    Process user input with filler support:
    1. Check if filler should be used (85% chance, skip for opening/closing)
    2. Start LLM processing in parallel
    3. Play filler if selected
    4. Wait for LLM response
    5. Play LLM response after filler completes (if LLM finishes while filler is playing, wait)
    """
    state = connection_states.get(websocket_id)
    if not state:
        return
    
    # Check if this is opening (first user input) or will result in closing
    is_opening = not session.get("conversation_started", False)
    phase = session.get("phase", "conversation")
    is_closing_phase = phase == "closing"
    
    # Get current question text for similarity search (if available)
    current_question = None
    try:
        from flow.flow_manager import get_question_text
        current_question = get_question_text(session)
    except Exception as e:
        logger.debug(f"Could not get current question: {e}")
    
    # Check if we should use filler (85% probability, skip for opening/closing)
    # Pass transcript and question for similarity-based filler selection
    filler_text = get_filler(
        transcript=transcription,
        question=current_question,
        skip_for_opening=is_opening,
        skip_for_closing=is_closing_phase,
        use_similarity=True
    )
    use_filler = filler_text is not None
    
    # Also check if result will be closing (to skip filler)
    # We'll check this after LLM processing
    
    # Start LLM processing in parallel (run in executor since process_answer is sync)
    loop = asyncio.get_event_loop()
    llm_task = loop.run_in_executor(None, process_answer, session, transcription)
    
    filler_playing = False
    filler_task = None
    
    # Play filler if selected (this will start playing immediately)
    if use_filler:
        logger.info(f"🎭 Playing filler: '{filler_text}' (LLM processing in parallel)")
        filler_playing = True
        filler_task = asyncio.create_task(
            send_tts_and_wait(websocket_id, filler_text, response_audio_base)
        )
    
    # Wait for LLM processing to complete
    try:
        result = await llm_task
        logger.info(f"📤 LLM result: {result}")
        save_session(session)
        
        # Check if result indicates closing (skip filler for closing responses)
        is_closing_result = result in ["CLOSING", "END"]
        
        # If LLM finished before filler started or finished, log it
        if use_filler and filler_task:
            if filler_task.done():
                logger.info("✅ LLM finished after filler completed")
            else:
                logger.info("⏳ LLM finished, waiting for filler to complete...")
    except Exception as e:
        logger.error(f"❌ Error in LLM processing: {e}")
        result = "REPEAT"
        is_closing_result = False
    
    # Wait for filler to finish if it's still playing (unless it's a closing result)
    # This ensures LLM response plays AFTER filler completes
    if filler_playing and filler_task and not is_closing_result:
        try:
            await filler_task
            logger.info("✅ Filler playback completed, now playing LLM response")
        except Exception as e:
            logger.error(f"❌ Error waiting for filler: {e}")
    elif is_closing_result and filler_playing and filler_task:
        # For closing, cancel filler if still playing
        logger.info("🚫 Cancelling filler for closing statement")
        filler_task.cancel()
        try:
            await filler_task
        except asyncio.CancelledError:
            pass
    
    # Now process the result and play response
    if result == "CONTINUE_CONVERSATION":
        logger.info("💬 Continuing conversation")
        from flow.flow_manager import get_conversation_response_text
        response_text = get_conversation_response_text(session)
        save_session(session)
        await send_tts(websocket_id, response_text, audio_base=response_audio_base)
    
    elif result == "CLOSING":
        ack_text = session.get("acknowledgment_text")
        if ack_text:
            logger.info(f"💬 Speaking acknowledgment: {ack_text}")
            await send_tts(websocket_id, ack_text, audio_base=response_audio_base)
            session.pop("acknowledgment_text", None)
            save_session(session)
        
        logger.info("👋 Saying closing statement...")
        closing_text = get_closing_text(session)
        save_session(session)
        save_session_data(state.get("session_id"), session)
        await send_tts(websocket_id, closing_text, audio_base=response_audio_base)
        state["pending_end"] = True
        state["timeout_monitoring"] = False
    
    elif result == "END":
        logger.info("❌ Max retries exceeded, saying closing...")
        closing_text = get_closing_text(session)
        save_session(session)
        save_session_data(state.get("session_id"), session)
        await send_tts(websocket_id, closing_text, audio_base=response_audio_base)
        state["pending_end"] = True
        state["timeout_monitoring"] = False
    
    elif result in ["NEXT", "REPEAT"]:
        question_text = get_question_text(session)
        save_session(session)
        logger.info(f"📋 Next question: {question_text[:50] if question_text else 'None'}...")
        
        if question_text:
            await send_tts(websocket_id, question_text, audio_base=response_audio_base)
        else:
            logger.info("📝 No more questions, generating summary...")
            session["phase"] = "summary"
            summary_text = get_summary_text(session)
            save_session(session)
            await send_tts(websocket_id, summary_text)
            state["pending_confirmation"] = True
    else:
        logger.warning(f"⚠️ Unknown result from process_answer: {result}")


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

            turn_base = None
            session_created = False

            if transcription:
                state["last_user_input_time"] = time.time()
                logger.info(f"⏰ Updated last_user_input_time for {websocket_id}")

                if not state.get("session_id"):
                    # Create session with name
                    logger.info(f"Creating session with name: {transcription}")
                    try:
                        from  sessions.session_schema import create_session
                        from  sessions.session_store import (
                            save_session as save_session_store,
                        )
                        import uuid
                        from datetime import datetime

                        session_id = f"session_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"
                        session = create_session(session_id, transcription.strip())
                        save_session_store(session)
                        state["session_id"] = session_id
                        session_created = True

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
                            turn_base = _next_turn_base(state, session_id)
                            state["current_turn_base"] = turn_base
                            await send_tts(
                                websocket_id, question_text, audio_base=turn_base
                            )
                    except Exception as e:
                        logger.error(f"Error creating session: {e}")
                    if session_created:
                        # Save the initial ASR audio for this session
                        turn_base = turn_base or _next_turn_base(
                            state, state.get("session_id") or websocket_id
                        )
                        asr_file = f"{turn_base}.wav"
                        audio_bytes_wav = _prepare_audio_bytes(audio_bytes)
                        _save_audio_non_blocking(
                            ASR_AUDIO_DIR / asr_file,
                            audio_bytes_wav,
                        )
                        state["last_asr_audio_url"] = _build_audio_url(
                            "asr_audios", asr_file
                        )
                        state["last_transcription"] = transcription
                    continue

                # Save ASR audio for existing session
                if state.get("session_id"):
                    turn_base = _next_turn_base(
                        state, state.get("session_id") or websocket_id
                    )
                    state["current_turn_base"] = turn_base
                    asr_file = f"{turn_base}.wav"
                    audio_bytes_wav = _prepare_audio_bytes(audio_bytes)
                    _save_audio_non_blocking(ASR_AUDIO_DIR / asr_file, audio_bytes_wav)
                    state["last_asr_audio_url"] = _build_audio_url(
                        "asr_audios", asr_file
                    )
                    state["last_transcription"] = transcription

                # Process answer with filler support
                session_id = state["session_id"]
                session = get_session(session_id)
                response_audio_base = state.get("current_turn_base")

                if session:
                    logger.info(
                        f"📥 Processing answer: '{transcription}' for phase={session.get('phase', 'questions')}, question={session.get('current_question')}"
                    )
                    # Use new process_with_filler function that handles filler + LLM in parallel
                    await process_with_filler(
                        websocket_id, session, transcription, response_audio_base
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

            # Support both legacy 3-tuple and new 4-tuple with audio base name
            if len(item) == 4:
                websocket, text, utterance_id, audio_base = item
            else:
                websocket, text, utterance_id = item
                audio_base = None

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

            if state and audio_base is None:
                audio_base = state.get("current_turn_base")
            if state and audio_base is None:
                audio_base = _next_turn_base(
                    state, state.get("session_id") or websocket_id
                )
                state["current_turn_base"] = audio_base

            logger.info(f"🗣️ TTS playing: {text[:50]}...")
            # Send bot_message so frontend can display the question
            await websocket.send_json({"type": "bot_message", "text": text})
            await websocket.send_json({"type": "tts_start", "text": text})

            chunk_count = 0
            audio_buffer = bytearray()
            async for audio_chunk in synthesize_stream(text):
                if audio_chunk:
                    audio_buffer.extend(audio_chunk)
                    await websocket.send_bytes(audio_chunk)
                    chunk_count += 1

            await websocket.send_json({"type": "tts_end", "chunks_sent": chunk_count})
            logger.info(f"✅ TTS complete: {chunk_count} chunks sent")
            
            # Call TTS finished callback if set
            if state and state.get("_tts_finished_callback"):
                callback = state.get("_tts_finished_callback")
                if callable(callback):
                    try:
                        callback()
                    except Exception as e:
                        logger.error(f"❌ Error in TTS finished callback: {e}")

            tts_audio_url = None
            if audio_buffer:
                base_name = audio_base or _sanitize_session_id(
                    (state or {}).get("session_id") or websocket_id
                )
                file_name = f"{base_name}.wav"
                audio_bytes = _prepare_audio_bytes(bytes(audio_buffer))
                _save_audio_non_blocking(TTS_AUDIO_DIR / file_name, audio_bytes)
                tts_audio_url = _build_audio_url("tts_audios", file_name)
                if state:
                    state["last_tts_audio_url"] = tts_audio_url

            if state:
                state["tts_playing"] = False
                if not state.get("processing_asr"):
                    state["last_user_input_time"] = time.time()
                    logger.info(f"⏰ Reset last_user_input_time after TTS for {websocket_id}")

            if utterance_id:
                record_event(utterance_id, "TTS_COMPLETE")
                cleanup_tracking(utterance_id)

            await _log_interaction_if_ready(websocket_id, text, tts_audio_url)

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
