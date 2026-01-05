"""WebSocket routes for audio streaming"""
import json
import asyncio
import logging
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from services.vad_processor import process_frame, cleanup_connection
from services.asr_service import transcribe_audio
from services.tts_service import synthesize_stream
from queues.asr_queue import asr_queue
from queues.tts_queue import tts_queue
from utils.latency_tracker import record_event, cleanup
from sessions.session_store import get_session, save_session
from flow.flow_manager import get_question_text, process_answer

logger = logging.getLogger(__name__)

# Track active connections and their states
active_connections: Dict[str, WebSocket] = {}
connection_states: Dict[str, Dict] = {}  # {websocket_id: {mic_enabled, session_id, tts_playing}}


async def get_websocket_id(websocket: WebSocket) -> str:
    """Get or create a unique ID for the WebSocket connection"""
    # Use the connection object's id or create one
    if not hasattr(websocket, '_id'):
        websocket._id = id(websocket)
    return str(websocket._id)


async def websocket_audio_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for bidirectional audio streaming"""
    await websocket.accept()
    websocket_id = await get_websocket_id(websocket)
    active_connections[websocket_id] = websocket
    
    # Initialize connection state
    connection_states[websocket_id] = {
        "mic_enabled": False,  # Start with mic disabled (wait for TTS to finish)
        "session_id": None,
        "tts_playing": False,
        "processing_asr": False
    }
    
    logger.info(f"✅ WebSocket connected: {websocket_id}")
    
    try:
        # Start background tasks
        asr_processor_task = asyncio.create_task(process_asr_queue(websocket_id))
        tts_processor_task = asyncio.create_task(process_tts_queue(websocket_id))
        
        # Main message loop
        while True:
            try:
                # Receive message from client
                message = await websocket.receive()
                
                # Handle text messages (control messages)
                if "text" in message:
                    data = json.loads(message["text"])
                    await handle_control_message(websocket_id, data)
                
                # Handle binary messages (audio frames) - continuous streaming to VAD
                elif "bytes" in message:
                    audio_frame = message["bytes"]
                    state = connection_states[websocket_id]
                    
                    # Log audio frame reception
                    if not hasattr(state, "_frame_count"):
                        state["_frame_count"] = 0
                    state["_frame_count"] += 1
                    if state["_frame_count"] <= 5 or state["_frame_count"] % 100 == 0:
                        logger.info(f"📥 Backend: Received audio frame #{state['_frame_count']} from {websocket_id}, size: {len(audio_frame)} bytes")
                    
                    # Continuously process audio frames through VAD when mic is enabled
                    if state["mic_enabled"] and not state["processing_asr"]:
                        logger.debug(f"🔄 Backend: Processing frame #{state['_frame_count']} through VAD for {websocket_id}")
                        await process_frame(
                            websocket_id,
                            audio_frame,
                            mic_enabled=state["mic_enabled"]
                        )
                    elif not state["mic_enabled"]:
                        # Mic disabled (TTS playing or processing) - ignore audio frames
                        if state["_frame_count"] <= 5:
                            logger.debug(f"⏸️ Backend: Ignoring frame (mic disabled, TTS playing or processing)")
                    elif state["processing_asr"]:
                        # ASR processing - ignore audio frames to prevent overlap
                        if state["_frame_count"] <= 5:
                            logger.debug(f"⏸️ Backend: Ignoring frame (ASR processing)")
                
            except WebSocketDisconnect:
                logger.info(f"❌ WebSocket disconnected: {websocket_id}")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}")
                import traceback
                traceback.print_exc()
                break
                
    finally:
        # Cleanup
        cleanup_connection(websocket_id)
        if websocket_id in active_connections:
            del active_connections[websocket_id]
        if websocket_id in connection_states:
            del connection_states[websocket_id]
        
        # Cancel background tasks
        asr_processor_task.cancel()
        tts_processor_task.cancel()
        
        try:
            await asr_processor_task
        except asyncio.CancelledError:
            pass
        try:
            await tts_processor_task
        except asyncio.CancelledError:
            pass


async def handle_control_message(websocket_id: str, data: Dict):
    """Handle control messages from client"""
    message_type = data.get("type")
    state = connection_states.get(websocket_id)
    
    if not state:
        logger.warning(f"No state found for websocket {websocket_id}")
        return
    
    if message_type == "init_session":
        # Initialize session
        session_id = data.get("session_id")
        if session_id:
            state["session_id"] = session_id
            logger.info(f"Session initialized: {session_id} for {websocket_id}")
            
            # Get first question and send via TTS
            session = get_session(session_id)
            if session:
                question_text = get_question_text(session)
                if question_text:
                    await send_tts(websocket_id, question_text)
    
    elif message_type == "start_call":
        # User clicked start call button - ask for name
        logger.info(f"Start call requested for {websocket_id}")
        name_request_text = "Namaste! Kripya apna naam boliye."
        await send_tts(websocket_id, name_request_text)
    
    elif message_type == "tts_finished":
        # Client confirms TTS playback finished - enable mic
        state["mic_enabled"] = True
        state["tts_playing"] = False
        logger.info(f"🎤 Mic enabled for {websocket_id}")
        
        # Send confirmation to client
        websocket = active_connections.get(websocket_id)
        if websocket:
            await websocket.send_json({
                "type": "mic_enabled",
                "message": "Microphone is now active"
            })
    
    elif message_type == "tts_started":
        # Client started TTS playback - disable mic
        state["mic_enabled"] = False
        state["tts_playing"] = True
        logger.info(f"🔇 Mic disabled for {websocket_id} (TTS playing)")
    
    elif message_type == "tts_request":
        # Client requests TTS for specific text
        text = data.get("text")
        if text:
            await send_tts(websocket_id, text)
    
    elif message_type == "ping":
        # Heartbeat
        websocket = active_connections.get(websocket_id)
        if websocket:
            await websocket.send_json({"type": "pong"})


async def process_asr_queue(websocket_id: str):
    """Process ASR queue items"""
    while websocket_id in active_connections:
        try:
            # Get item from queue (with timeout to check if connection still exists)
            try:
                item = await asyncio.wait_for(asr_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            
            ws_id, audio_bytes, utterance_id = item
            
            # Only process if it's for this connection
            if ws_id != websocket_id:
                # Put it back for another processor
                await asr_queue.put(item)
                continue
            
            state = connection_states.get(websocket_id)
            if not state:
                continue
            
            # Mark as processing ASR (disable mic during processing)
            state["processing_asr"] = True
            state["mic_enabled"] = False
            
            logger.info(f"🔍 ASR: Processing audio for {websocket_id}")
            logger.info(f"🔍 ASR: Audio size: {len(audio_bytes)} bytes")
            
            # Transcribe audio
            result = await transcribe_audio(audio_bytes)
            transcription = result.get("transcription", "").strip()
            
            if utterance_id:
                record_event(utterance_id, "ASR_COMPLETE")
            
            # Process transcription if valid
            if transcription:
                # If no session_id yet, this is the name - create session
                if not state.get("session_id"):
                    logger.info(f"Creating session with name: {transcription}")
                    try:
                        # Create session via API (we need to import the function)
                        from sessions.session_schema import create_session
                        from sessions.session_store import save_session as save_session_store
                        import uuid
                        from datetime import datetime
                        
                        session_id = f"session_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"
                        session = create_session(session_id, transcription.strip())
                        save_session_store(session)
                        state["session_id"] = session_id
                        
                        # Send session_id to frontend
                        websocket = active_connections.get(websocket_id)
                        if websocket:
                            await websocket.send_json({
                                "type": "session_created",
                                "session_id": session_id,
                                "customer_name": transcription.strip()
                            })
                        
                        # Get first question and send via TTS
                        question_text = get_question_text(session)
                        save_session_store(session)
                        
                        if question_text:
                            logger.info(f"Sending first question via TTS: {question_text}")
                            await send_tts(websocket_id, question_text)
                        else:
                            logger.warning("No first question found")
                    except Exception as e:
                        logger.error(f"Error creating session: {e}")
                        import traceback
                        traceback.print_exc()
                    continue
                
                # If session exists, process as answer
                session_id = state["session_id"]
                session = get_session(session_id)
                
                if session:
                    # Process answer through flow manager
                    result = process_answer(session, transcription)
                    save_session(session)
                    
                    # Get next question or handle completion
                    if result == "COMPLETED":
                        # Survey completed
                        websocket = active_connections.get(websocket_id)
                        if websocket:
                            await websocket.send_json({
                                "type": "survey_completed",
                                "message": "Survey completed successfully"
                            })
                        state["mic_enabled"] = False
                        continue
                    elif result == "END":
                        # Max retries exceeded
                        websocket = active_connections.get(websocket_id)
                        if websocket:
                            await websocket.send_json({
                                "type": "survey_ended",
                                "message": "Maximum retries exceeded"
                            })
                        state["mic_enabled"] = False
                        continue
                    elif result in ["NEXT", "REPEAT"]:
                        # Get next question
                        question_text = get_question_text(session)
                        save_session(session)
                        
                        if question_text:
                            # Send question via TTS
                            await send_tts(websocket_id, question_text)
                        else:
                            # No more questions
                            websocket = active_connections.get(websocket_id)
                            if websocket:
                                await websocket.send_json({
                                    "type": "survey_completed",
                                    "message": "No more questions"
                                })
                            state["mic_enabled"] = False
                    else:
                        # Unknown result, re-enable mic
                        state["mic_enabled"] = True
            
            # Re-enable mic after processing (if TTS is not playing)
            # This allows continuous streaming to VAD for next utterance
            if not state.get("tts_playing"):
                state["mic_enabled"] = True
                logger.info(f"🎤 Mic re-enabled for continuous VAD streaming: {websocket_id}")
            state["processing_asr"] = False
            
            # Send transcription result to client
            websocket = active_connections.get(websocket_id)
            if websocket:
                await websocket.send_json({
                    "type": "transcription",
                    "text": transcription,
                    "detected_language": result.get("detected_language"),
                    "language_confidence": result.get("language_confidence")
                })
            
            if utterance_id:
                cleanup(utterance_id)
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error processing ASR: {e}")
            import traceback
            traceback.print_exc()
            state = connection_states.get(websocket_id)
            if state:
                state["processing_asr"] = False
                if not state.get("tts_playing"):
                    state["mic_enabled"] = True


async def process_tts_queue(websocket_id: str):
    """Process TTS queue items"""
    while websocket_id in active_connections:
        try:
            # Get item from queue
            try:
                item = await asyncio.wait_for(tts_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            
            ws_id, text, language, utterance_id = item
            
            # Only process if it's for this connection
            if ws_id != websocket_id:
                # Put it back for another processor
                await tts_queue.put(item)
                continue
            
            websocket = active_connections.get(websocket_id)
            if not websocket:
                continue
            
            state = connection_states.get(websocket_id)
            if state:
                state["tts_playing"] = True
                state["mic_enabled"] = False
            
            # Notify client that TTS is starting
            await websocket.send_json({
                "type": "tts_start",
                "text": text
            })
            
            # Stream TTS audio
            chunk_count = 0
            async for audio_chunk in synthesize_stream(text):
                await websocket.send_bytes(audio_chunk)
                chunk_count += 1
            
            # Notify client that TTS is finished
            await websocket.send_json({
                "type": "tts_end",
                "chunks_sent": chunk_count
            })
            
            # Update state - mic will be enabled when client confirms TTS finished
            if state:
                state["tts_playing"] = False
                # Don't enable mic here - wait for client confirmation
            
            if utterance_id:
                record_event(utterance_id, "TTS_COMPLETE")
                cleanup(utterance_id)
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error processing TTS: {e}")
            import traceback
            traceback.print_exc()
            state = connection_states.get(websocket_id)
            if state:
                state["tts_playing"] = False
                if not state.get("processing_asr"):
                    state["mic_enabled"] = True


async def send_tts(websocket_id: str, text: str, language: str = None):
    """Send text to TTS queue for synthesis"""
    await tts_queue.put((websocket_id, text, language, None))

