from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
import time
from datetime import datetime
from database import get_db_connection
from services.bot_logic import start_conversation, handle_identity_reply

app = FastAPI()

class StartRequest(BaseModel):
    session_id: str
    customer_id: int   # INTERNAL

class ReplyRequest(BaseModel):
    session_id: str
    message: str


@app.post("/bot/start")
def bot_start(data: StartRequest):
    reply = start_conversation(data.customer_id, data.session_id)
    return {"reply": reply}


@app.post("/bot/reply")
def bot_reply(data: ReplyRequest):
    start_time = time.perf_counter()   # high precision
    reply = handle_identity_reply(data.message, data.session_id)
    end_time = time.perf_counter()     # high precision
    latency_ms = round((end_time - start_time) * 1000, 3)
    return {
    "reply": reply,
    "latency_ms": latency_ms,
    "timestamp": datetime.now().isoformat()
    }




app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/customers")
def get_customers():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, customer_name FROM ltfs_customers LIMIT 50")
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [
        {"id": row[0], "name": row[1]}
        for row in rows
    ]
