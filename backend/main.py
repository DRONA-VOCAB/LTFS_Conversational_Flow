from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import uuid
import json

from database import get_db, CustomerData
from models.conversation import ConversationState
from services.conversation_manager import ConversationManager
from services.asr_service import transcribe_audio
from services.tts_service import synthesize_speech

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
                "state": c.state
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
            "area": customer.area
        }
    except HTTPException:
        raise
    except Exception as e:
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
            customer_id=customer_id,
            customer_name=customer.customer_name
        )
        
        active_conversations[session_id] = conversation_manager
        
        # Get first question
        first_question = conversation_manager.get_current_question()
        
        return {
            "session_id": session_id,
            "customer_id": customer_id,
            "customer_name": customer.customer_name,
            "first_question": first_question["text"] if first_question else None,
            "question_number": 1
        }
    except HTTPException:
        raise
    except Exception as e:
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
    """WebSocket endpoint for real-time voice conversation"""
    await websocket.accept()
    
    if session_id not in active_conversations:
        await websocket.send_json({
            "type": "error",
            "message": "Session not found"
        })
        await websocket.close()
        return
    
    conversation_manager = active_conversations[session_id]
    
    try:
        # Send first question - bot speaks first
        first_question = conversation_manager.get_current_question()
        if first_question:
            # Convert text to speech and send audio FIRST
            audio_data = await synthesize_speech(first_question["text"])
            if audio_data:
                await websocket.send_bytes(audio_data)
            # Then send JSON metadata (audio plays, then recording starts)
            await websocket.send_json({
                "type": "question",
                "text": first_question["text"],
                "question_number": first_question["number"]
            })
        
        while True:
            # Wait for audio input from customer
            data = await websocket.receive()
            
            if "bytes" in data:
                # Audio data received from customer (WebM format from browser)
                audio_bytes = data["bytes"]
                
                # Stop recording indicator on frontend (will be handled by response)
                
                # Convert speech to text
                transcribed_text = await transcribe_audio(audio_bytes, content_type="audio/webm")
                
                if transcribed_text:
                    # Process customer response
                    result = await conversation_manager.process_customer_response(transcribed_text)
                    
                    # Send bot response as audio FIRST, then JSON
                    if result.get("bot_text"):
                        audio_data = await synthesize_speech(result["bot_text"])
                        if audio_data:
                            await websocket.send_bytes(audio_data)
                    
                    # Send JSON response metadata
                    await websocket.send_json({
                        "type": "response",
                        "bot_text": result.get("bot_text"),
                        "transcribed_text": transcribed_text,
                        "should_proceed": result.get("should_proceed", False),
                        "conversation_complete": result.get("conversation_complete", False),
                        "current_question": conversation_manager.state.current_question + 1
                    })
                    
                    if result.get("conversation_complete"):
                        # Send final summary after a brief delay
                        summary = conversation_manager.get_conversation_summary()
                        await websocket.send_json({
                            "type": "summary",
                            "data": summary
                        })
                        break
            
            elif "text" in data:
                # JSON message received
                message = json.loads(data["text"])
                
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif message.get("type") == "end_call":
                    break
                elif message.get("type") == "audio_finished":
                    # Client notification that audio playback finished (optional)
                    pass
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
    finally:
        # Clean up
        if session_id in active_conversations:
            del active_conversations[session_id]
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

