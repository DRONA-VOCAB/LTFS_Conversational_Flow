from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import uuid
import json
import logging

from database import get_db, CustomerData
from models.conversation import ConversationState
from services.conversation_manager import ConversationManager
from services.asr_service import transcribe_audio
from services.tts_service import synthesize_speech
from services.vad_service import (
    process_frame as vad_process_frame,
    cleanup_connection as vad_cleanup,
    vad_model_loaded,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="L&T Finance Voice Feedback System")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active conversations
active_conversations: dict[str, ConversationManager] = {}


# Initialize VAD service on startup
@app.on_event("startup")
async def startup_event():
    """Initialize VAD service on application startup"""
    logger.info("🚀 Starting up application...")
    try:
        if vad_model_loaded:
            logger.info("✅ VAD service initialized successfully")
        else:
            logger.warning(
                "⚠️ VAD service initialized but model not loaded (PyTorch/Silero may not be available)"
            )
    except Exception as e:
        logger.error(f"❌ Failed to initialize VAD service: {e}", exc_info=True)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("🛑 Shutting down application...")


@app.get("/")
async def root():
    return {"message": "L&T Finance Voice Feedback API"}


@app.get("/api/customers", response_model=List[dict])
async def get_customers(db: Session = Depends(get_db), skip: int = 0, limit: int = 100):
    """Get list of customers from database"""
    try:
        customers = db.query(CustomerData).offset(skip).limit(limit).all()
        return [
            {
                "id": c.id,
                "customer_name": c.customer_name,
                "contact_number": c.contact_number,
                "agreement_no": c.agreement_no,
                "product": c.product,
                "branch": c.branch,
                "state": c.state,
            }
            for c in customers
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/customers/{customer_id}")
async def get_customer(customer_id: int, db: Session = Depends(get_db)):
    """Get specific customer details"""
    try:
        customer = db.query(CustomerData).filter(CustomerData.id == customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        return {
            "id": customer.id,
            "customer_name": customer.customer_name,
            "contact_number": customer.contact_number,
            "agreement_no": customer.agreement_no,
            "product": customer.product,
            "branch": customer.branch,
            "state": customer.state,
            "zone": customer.zone,
            "area": customer.area,
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/call/start/{customer_id}")
async def start_call(customer_id: int, db: Session = Depends(get_db)):
    """Start a new call session for a customer"""
    try:
        customer = db.query(CustomerData).filter(CustomerData.id == customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        if not customer.customer_name:
            raise HTTPException(status_code=400, detail="Customer name not available")

        # Create conversation manager
        session_id = str(uuid.uuid4())
        conversation_manager = ConversationManager(
            customer_id=customer_id, customer_name=customer.customer_name
        )

        active_conversations[session_id] = conversation_manager

        # Get first question
        first_question = conversation_manager.get_current_question()

        return {
            "session_id": session_id,
            "customer_id": customer_id,
            "customer_name": customer.customer_name,
            "first_question": first_question["text"] if first_question else None,
            "question_number": 1,
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/call/{session_id}/summary")
async def get_call_summary(session_id: str):
    """Get conversation summary"""
    if session_id not in active_conversations:
        raise HTTPException(status_code=404, detail="Session not found")

    manager = active_conversations[session_id]
    return manager.get_conversation_summary()


@app.websocket("/ws/call/{session_id}")
async def websocket_call(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time voice conversation with VAD"""
    await websocket.accept()
    logger.info(f"✅ WebSocket connected for session: {session_id}")

    if session_id not in active_conversations:
        await websocket.send_json({"type": "error", "message": "Session not found"})
        await websocket.close()
        return

    conversation_manager = active_conversations[session_id]

    # Store VAD state per connection
    websocket.vad_state = {
        "frames_received": 0,
        "speech_detected_count": 0,
        "no_speech_count": 0,
    }

    # Send VAD status to client
    await websocket.send_json(
        {
            "type": "vad_status",
            "vad_loaded": vad_model_loaded,
            "message": "VAD ready" if vad_model_loaded else "VAD not available",
        }
    )

    async def handle_utterance(utterance_pcm_bytes: bytes):
        """Handle detected speech utterance"""
        print(f"\n{'='*80}")
        print(f"🎤 UTTERANCE DETECTED - Session: {session_id}")
        print(
            f"   Utterance size: {len(utterance_pcm_bytes)} bytes ({len(utterance_pcm_bytes) / (16000 * 2):.2f}s)"
        )
        print(f"{'='*80}\n")
        logger.info(
            f"🎤 Utterance detected for session {session_id}: "
            f"{len(utterance_pcm_bytes)} bytes ({len(utterance_pcm_bytes) / (16000 * 2):.2f}s)"
        )

        # Convert PCM to WAV for ASR
        from services.audio_converter import pcm_to_wav

        try:
            wav_bytes = pcm_to_wav(
                utterance_pcm_bytes, sample_rate=16000, channels=1, sample_width=2
            )
            logger.info(
                f"✅ Converted PCM to WAV: {len(utterance_pcm_bytes)} bytes → {len(wav_bytes)} bytes"
            )
        except Exception as e:
            logger.error(f"❌ Error converting PCM to WAV: {e}", exc_info=True)
            wav_bytes = utterance_pcm_bytes  # Fallback to raw PCM

        # Convert speech to text
        print(f"\n{'='*80}")
        print(f"🔊 SENDING TO ASR SERVICE...")
        print(f"   Audio size: {len(wav_bytes)} bytes")
        print(f"{'='*80}\n")
        logger.info(f"🔊 Sending utterance to ASR service ({len(wav_bytes)} bytes)")

        transcribed_text = await transcribe_audio(wav_bytes, content_type="audio/wav")

        if transcribed_text:
            print(f"\n{'='*80}")
            print(f"✅ ASR TRANSCRIPTION RECEIVED:")
            print(f"   Text: '{transcribed_text}'")
            print(f"   Length: {len(transcribed_text)} characters")
            print(f"{'='*80}\n")
            logger.info(f"✅ ASR Transcription: '{transcribed_text}'")

            # Get current conversation state
            current_step = conversation_manager.state.current_question
            print(f"\n{'='*80}")
            print(f"📊 CONVERSATION STATE:")
            print(f"   Current Step: {current_step}")
            print(f"   Session ID: {session_id}")
            print(f"{'='*80}\n")
            logger.info(f"📊 Current conversation step: {current_step}")

            # Process customer response
            print(f"\n{'='*80}")
            print(f"🤖 PROCESSING WITH CONVERSATION MANAGER...")
            print(f"   User input: '{transcribed_text}'")
            print(f"{'='*80}\n")
            logger.info(f"🤖 Processing customer response with conversation manager")

            result = await conversation_manager.process_customer_response(
                transcribed_text
            )

            print(f"\n{'='*80}")
            print(f"🤖 CONVERSATION MANAGER RESULT:")
            print(f"   Should proceed: {result.get('should_proceed', False)}")
            print(
                f"   Conversation complete: {result.get('conversation_complete', False)}"
            )
            print(f"   Bot response: '{result.get('bot_text', '')}'")
            print(f"{'='*80}\n")
            logger.info(
                f"🤖 Conversation manager result: "
                f"proceed={result.get('should_proceed')}, "
                f"complete={result.get('conversation_complete')}"
            )

            # Send bot response as audio ONLY if there's actual text (skip empty acknowledgments)
            bot_text = result.get("bot_text", "").strip()
            if bot_text:
                print(f"\n{'='*80}")
                print(f"🔊 GENERATING TTS AUDIO...")
                print(f"   Text: '{bot_text}'")
                print(f"   Length: {len(bot_text)} characters")
                print(f"{'='*80}\n")
                logger.info(f"🔊 Generating TTS for bot response: '{bot_text}'")

                # Set flag to pause VAD processing during TTS
                tts_playing = True
                logger.info("⏸️ Pausing audio streaming (TTS playing)")

                tts_result = await synthesize_speech(
                    bot_text, speed=1.2
                )  # 20% faster for normal pace
                if tts_result:
                    audio_data, sample_rate = tts_result
                    print(
                        f"✅ TTS generated: {len(audio_data)} bytes, sample rate: {sample_rate} Hz"
                    )
                    logger.info(
                        f"✅ TTS generated successfully: {len(audio_data)} bytes, sample rate: {sample_rate} Hz"
                    )
                    await websocket.send_bytes(audio_data)
                    print(f"📤 Sent TTS audio to client")
                    logger.info(
                        "📤 TTS audio sent to client, waiting for playback to finish..."
                    )
                else:
                    print(f"❌ TTS generation failed")
                    logger.error("❌ TTS generation failed")
                    tts_playing = False
            else:
                # No bot text - skip acknowledgment, go directly to next question
                logger.info("⏭️ Skipping acknowledgment, proceeding to next question")

            # Send JSON response metadata (this signals client that TTS finished)
            await websocket.send_json(
                {
                    "type": "response",
                    "bot_text": result.get("bot_text"),
                    "transcribed_text": transcribed_text,
                    "should_proceed": result.get("should_proceed", False),
                    "conversation_complete": result.get("conversation_complete", False),
                    "current_question": conversation_manager.state.current_question + 1,
                }
            )

            # Resume VAD processing after TTS (client will resume streaming)
            tts_playing = False
            logger.info("▶️ Resuming audio streaming (TTS finished)")

            print(f"\n{'='*80}")
            print(f"📤 SENT RESPONSE TO CLIENT")
            print(f"   Transcription: '{transcribed_text}'")
            print(f"   Bot text: '{result.get('bot_text', '')}'")
            print(
                f"   Next question: {conversation_manager.state.current_question + 1}"
            )
            print(f"   Audio streaming: RESUMED")
            print(f"{'='*80}\n")

            if result.get("conversation_complete"):
                # Send final summary after a brief delay
                summary = conversation_manager.get_conversation_summary()
                print(f"\n{'='*80}")
                print(f"✅ CONVERSATION COMPLETE!")
                print(f"   Summary: {summary}")
                print(f"{'='*80}\n")
                logger.info(f"✅ Conversation complete. Summary: {summary}")
                await websocket.send_json({"type": "summary", "data": summary})
                return True  # Signal to break loop

            # If should_proceed is True, ask the next question immediately
            if result.get("should_proceed", False) and not result.get(
                "conversation_complete", False
            ):
                # Get the next question using the updated current_question index
                next_question = conversation_manager.get_current_question()
                print(f"\n{'='*80}")
                print(f"🔍 DEBUG - Getting next question:")
                print(
                    f"   Current question index: {conversation_manager.state.current_question}"
                )
                print(
                    f"   Next question number from result: {result.get('next_question_number')}"
                )
                print(f"{'='*80}\n")

                if next_question:
                    print(f"\n{'='*80}")
                    print(f"📢 ASKING NEXT QUESTION...")
                    print(f"   Question: '{next_question['text']}'")
                    print(f"   Question number: {next_question['number']}")
                    print(f"{'='*80}\n")
                    logger.info(f"📢 Asking next question: '{next_question['text']}'")

                    # Set flag to pause VAD during TTS
                    tts_playing = True
                    logger.info("⏸️ Pausing audio streaming (TTS playing)")

                    # Convert text to speech and send audio
                    tts_result = await synthesize_speech(
                        next_question["text"], speed=1.2
                    )
                    if tts_result:
                        audio_data, sample_rate = tts_result
                        await websocket.send_bytes(audio_data)
                        print(
                            f"✅ Sent audio for next question ({len(audio_data)} bytes, sample rate: {sample_rate} Hz)"
                        )
                        logger.info(
                            f"✅ Sent audio for next question ({len(audio_data)} bytes, sample rate: {sample_rate} Hz)"
                        )

                    # Send JSON metadata
                    await websocket.send_json(
                        {
                            "type": "question",
                            "text": next_question["text"],
                            "question_number": next_question["number"],
                        }
                    )

                    # Resume streaming after question is sent
                    tts_playing = False
                    logger.info("▶️ Audio streaming resumed after next question")
        else:
            print(f"\n{'='*80}")
            print(f"⚠️ NO TRANSCRIPTION RETURNED")
            print(f"   ASR service returned empty result")
            print(f"{'='*80}\n")
            logger.warning(f"⚠️ No transcription returned for utterance")

        return False

    def on_no_speech(audio_bytes: bytes, reason: str):
        """Callback when no speech is detected"""
        websocket.vad_state["no_speech_count"] += 1
        if websocket.vad_state["no_speech_count"] % 50 == 0:  # Log every 50 frames
            logger.debug(
                f"🔇 No speech detected (Frame {websocket.vad_state['frames_received']}, "
                f"Reason: {reason}, Total no-speech: {websocket.vad_state['no_speech_count']})"
            )

    # Flag to pause VAD processing when TTS is playing
    tts_playing = False

    try:
        # Send first question - bot speaks first
        first_question = conversation_manager.get_current_question()
        if first_question:
            print(f"\n{'='*80}")
            print(f"📢 SENDING FIRST QUESTION...")
            print(f"   Question: '{first_question['text']}'")
            print(f"   Question number: {first_question['number']}")
            print(f"{'='*80}\n")
            logger.info(f"📢 Sending first question: '{first_question['text']}'")

            # Set flag to pause VAD during initial TTS
            tts_playing = True
            logger.info("⏸️ Pausing audio streaming (initial TTS playing)")

            # Convert text to speech and send audio FIRST
            result = await synthesize_speech(first_question["text"])
            if result:
                audio_data, sample_rate = result
                await websocket.send_bytes(audio_data)
                print(
                    f"✅ Sent audio for first question ({len(audio_data)} bytes, sample rate: {sample_rate} Hz)"
                )
                logger.info(
                    f"✅ Sent audio for first question ({len(audio_data)} bytes, sample rate: {sample_rate} Hz)"
                )
            # Then send JSON metadata (audio plays, then streaming starts)
            await websocket.send_json(
                {
                    "type": "question",
                    "text": first_question["text"],
                    "question_number": first_question["number"],
                }
            )
            # Resume streaming after question is sent (client will wait for TTS to finish)
            tts_playing = False
            logger.info("▶️ Audio streaming will resume after TTS finishes")

        print(f"\n{'='*80}")
        print(f"🎤 CONTINUOUS AUDIO STREAMING STARTED")
        print(f"   Waiting for PCM frames from client...")
        print(f"{'='*80}\n")
        logger.info("🎤 Continuous audio streaming started, waiting for frames...")

        while True:
            # Wait for audio input from customer
            data = await websocket.receive()

            if "bytes" in data:
                # Audio frame received from customer (PCM format, 32ms frames)
                frame_bytes = data["bytes"]
                websocket.vad_state["frames_received"] += 1
                frame_num = websocket.vad_state["frames_received"]

                # Skip VAD processing if TTS is playing
                if tts_playing:
                    if frame_num % 50 == 0:  # Log every 50 frames when paused
                        logger.debug(f"⏸️ Frame {frame_num} skipped (TTS playing)")
                    continue

                # Log first few frames
                if frame_num <= 5:
                    logger.info(
                        f"📥 Received frame {frame_num}: {len(frame_bytes)} bytes"
                    )

                if vad_model_loaded:
                    # Process frame directly through VAD (already PCM format)
                    from services.vad_service import FRAME_BYTES

                    # Ensure frame is correct size
                    if len(frame_bytes) != FRAME_BYTES:
                        if len(frame_bytes) < FRAME_BYTES:
                            # Pad with zeros
                            frame_bytes = frame_bytes + b"\x00" * (
                                FRAME_BYTES - len(frame_bytes)
                            )
                        else:
                            # Truncate
                            frame_bytes = frame_bytes[:FRAME_BYTES]

                    # Process frame through VAD
                    result = await vad_process_frame(
                        websocket,
                        frame_bytes,
                        on_speech_start=lambda fn=frame_num: print(
                            f"\n{'='*80}\n🎤 SPEECH STARTED - Frame {fn}\n{'='*80}\n"
                        )
                        or logger.info(f"🎤 SPEECH STARTED - Frame {fn}"),
                        on_speech_end=handle_utterance,
                        on_no_speech=on_no_speech,
                    )

                    websocket.vad_state["speech_detected_count"] += (
                        1 if result.get("is_speech") else 0
                    )

                    # Send speech detection status to client every 10 frames
                    if frame_num % 10 == 0 or result.get("is_speech"):
                        try:
                            await websocket.send_json(
                                {
                                    "type": "vad_update",
                                    "is_speech": result.get("is_speech", False),
                                    "probability": result.get("probability", 0.0),
                                    "is_speaking": result.get("is_speaking", False),
                                    "frame_number": frame_num,
                                    "speech_ratio": result.get("speech_ratio", 0.0),
                                    "rms": result.get("rms", 0.0),
                                }
                            )
                        except Exception as e:
                            logger.debug(f"Could not send VAD update: {e}")
                else:
                    # VAD not available - log warning
                    if frame_num % 100 == 0:
                        logger.warning(
                            f"⚠️ VAD not available, frame {frame_num} skipped"
                        )

            elif "text" in data:
                # JSON message received
                message = json.loads(data["text"])

                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif message.get("type") == "end_call":
                    logger.info(f"📞 Call ended by client for session: {session_id}")
                    break
                elif message.get("type") == "audio_finished":
                    # Client notification that audio playback finished (optional)
                    logger.debug("🔊 Client audio playback finished")

    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"❌ WebSocket error for session {session_id}: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        # Log final statistics
        if hasattr(websocket, "vad_state"):
            logger.info(
                f"📊 Session {session_id} statistics: "
                f"Frames={websocket.vad_state['frames_received']}, "
                f"Speech={websocket.vad_state['speech_detected_count']}, "
                f"No-speech={websocket.vad_state['no_speech_count']}"
            )

        # Clean up VAD state
        vad_cleanup(websocket)

        # Clean up
        if session_id in active_conversations:
            del active_conversations[session_id]
        await websocket.close()
        logger.info(f"🔌 WebSocket closed for session: {session_id}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
