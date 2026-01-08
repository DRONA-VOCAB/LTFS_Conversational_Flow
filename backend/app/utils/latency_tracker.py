import time
import logging
import asyncio
from typing import Dict, Any, Optional

# --- NEW IMPORT ---
# NOTE: Assuming save_record is defined in a 'data_persistence' module
from .data_persistence import save_record

logger = logging.getLogger(__name__)

# Dictionary to store tracking data, keyed by the unique Utterance ID.
# This allows multiple concurrent utterances from the same WebSocket.
# Value format: {'VAD_START': float, 'websocket_id': int, 'ASR_RECEIVED': float, ...}
latency_data: Dict[str, Dict[str, Any]] = {}


def get_websocket_id(websocket) -> int:
    """Uses the object's ID as a unique identifier for the connection."""
    return id(websocket)


def start_tracking(websocket, stream_sid: str = None) -> str:
    """
    Initializes tracking for a new utterance for a given WebSocket connection.
    Called when VAD detects the start of speech. Returns the new utterance_id.
    """
    start_time = time.time()
    ws_id = get_websocket_id(websocket)
    if stream_sid:
        utterance_id = stream_sid
    else:
        utterance_id = f"{ws_id}_{int(start_time * 1000)}"

    latency_data[utterance_id] = {
        "VAD_START": start_time,
        "websocket_id": ws_id,  # Store the WebSocket ID for reporting
    }
    logger.debug(
        f"[LATENCY] Tracking started for WS ID {ws_id}, Utterance ID: {utterance_id}"
    )
    return utterance_id


def record_event(utterance_id: str, event_name: str):
    """
    Records a specific timestamp event (e.g., ASR_RECEIVED, LLM_START).

    Uses utterance_id as the primary key.
    """
    if utterance_id in latency_data:
        latency_data[utterance_id][event_name] = time.time()
        logger.debug(
            f"[LATENCY] Recorded event '{event_name}' for Utterance ID: {utterance_id}"
        )
    else:
        logger.warning(
            f"[LATENCY] Cannot record event {event_name} - Utterance ID '{utterance_id}' not found."
        )


def cleanup_tracking(utterance_id: str):
    """
    Removes the completed tracking record from latency_data.
    """
    if utterance_id in latency_data:
        del latency_data[utterance_id]
        logger.debug(
            f"[LATENCY] Cleaned up tracking data for Utterance ID: {utterance_id}"
        )


async def calculate_and_report(websocket, utterance_id: str, final_transcription: str):
    """
    Calculates key latency metrics, reports them to the client via WebSocket,
    saves the record persistently, and clears the tracking data.
    """
    if utterance_id not in latency_data:
        logger.warning(f"[LATENCY] No data to report for Utterance ID {utterance_id}")
        return

    data = latency_data[utterance_id]
    ws_id = data["websocket_id"]

    # Ensure all critical timestamps exist before calculating
    if not all(
            k in data
            for k in [
                "VAD_START",
                "ASR_RECEIVED",
                "ASR_FINISHED",
                "LLM_FINISHED",
                "TTS_END",
            ]
    ):
        logger.warning(
            f"[LATENCY] Missing critical timestamps in data: {data}. Using current time as fallback."
        )

    try:
        # --- Core Latencies ---
        tts_end_time = data.get("TTS_END", time.time())
        tts_first_chunk = data.get("TTS_FIRST_CHUNK")
        # end_to_end = tts_end_time - data["VAD_START"] if "VAD_START" in data else None
        speech_end_time = data.get("VAD_END") or data.get("VAD_START")
        # end_to_end = tts_end_time - speech_end_time if speech_end_time else None
        end_to_end = tts_first_chunk - speech_end_time if speech_end_time else None

        asr_finished = data.get("ASR_FINISHED")
        asr_received = data.get("ASR_RECEIVED")
        asr_processing_latency = (
            asr_finished - asr_received if asr_received and asr_finished else None
        )

        llm_finished = data.get("LLM_FINISHED")
        llm_processing_latency = (
            llm_finished - asr_finished if asr_finished and llm_finished else None
        )

        # --- TTS Latency Calculation ---
        tts_start = llm_finished  # Time LLM finished (which is when TTS begins)
        tts_processing_latency = (
            tts_end_time - tts_start if tts_start and tts_end_time else None
        )
        # tts_first_chunk = data.get("TTS_FIRST_CHUNK")
        tts_start_latency = (
            tts_first_chunk - data.get("LLM_FINISHED")
            if tts_first_chunk and data.get("LLM_FINISHED")
            else None
        )

        # --- Persistent Record Structure (uses raw floats for metrics) ---
        record_data = {
            "timestamp_utc": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.gmtime(data["VAD_START"])
            ),
            "websocket_id": ws_id,
            "utterance_id": utterance_id,
            "transcription": final_transcription,
            "metrics": {
                "ASR_Processing_Latency_s": asr_processing_latency,
                "LLM_Processing_Latency_s": llm_processing_latency,
                # "TTS_Processing_Latency_s": tts_processing_latency,
                "TTS_First_Chunk_Latency_s": tts_start_latency,
                "End_To_End_s": end_to_end,
            },
            "raw_timestamps": data,
        }

        # 1. Save to persistent storage (JSON file)
        save_record(record_data)

        # 2. Prepare client-facing WebSocket message (formatting metrics to strings for readability)
        websocket_report = {
            "event": "latency_report",
            "utterance_id": utterance_id,
            "transcription": final_transcription,
            "latencies": {
                "asr_latency": asr_processing_latency,
                "llm_latency": llm_processing_latency,
                "tts_processing_latency": tts_start_latency,
                # "tts_latency": tts_processing_latency,
                "total_latency": end_to_end,
            },
            "metrics": {
                "VAD_Start_Time": data.get("VAD_START"),
                "ASR_Processing_Latency_s": (
                    f"{asr_processing_latency:.3f}" if asr_processing_latency else "N/A"
                ),
                "LLM_Processing_Latency_s": (
                    f"{llm_processing_latency:.3f}" if llm_processing_latency else "N/A"
                ),
                "TTS_Processing_Latency_s": (
                    f"{tts_start_latency:.3f}" if tts_start_latency else "N/A"
                ),
                # "TTS_Processing_Latency_s": (
                # f"{tts_processing_latency:.3f}" if tts_processing_latency else "N/A"
                # ),
                "End_To_End_s": f"{end_to_end:.3f}" if end_to_end else "N/A",
            },
            "raw_timestamps": data,
        }

        # 3. Send to the client
        await websocket.send_json(websocket_report)
        logger.info(
            f"[LATENCY REPORT] E2E: {websocket_report['metrics']['End_To_End_s']} for ID: {utterance_id}"
        )

    except Exception as e:
        logger.error(
            f"[LATENCY] Error calculating/reporting latency for Utterance ID {utterance_id}: {e}"
        )
    finally:
        # Cleanup
        cleanup_tracking(utterance_id)


# Utility to record and report event in one go (for LLM finished, TTS finished)
async def record_and_report(
        websocket, utterance_id: str, event_name: str, final_transcription: str = ""
):
    """
    Helper to record an event and trigger the final report for a specific utterance.
    The calling service MUST provide the utterance_id.
    """
    record_event(utterance_id, event_name)
    if event_name == "TTS_END":
        await calculate_and_report(websocket, utterance_id, final_transcription)