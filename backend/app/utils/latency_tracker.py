"""Latency tracking utility"""
import time
import uuid
from typing import Dict, Optional
from collections import defaultdict

# Store tracking data: {utterance_id: {event: timestamp}}
_tracking_data: Dict[str, Dict[str, float]] = defaultdict(dict)


def start_tracking(websocket_id: str) -> str:
    """Start tracking a new utterance"""
    utterance_id = str(uuid.uuid4())
    _tracking_data[utterance_id]["START"] = time.time()
    _tracking_data[utterance_id]["websocket_id"] = websocket_id
    return utterance_id


def record_event(utterance_id: str, event_name: str):
    """Record an event timestamp"""
    _tracking_data[utterance_id][event_name] = time.time()


def get_latency(utterance_id: str, start_event: str, end_event: str) -> Optional[float]:
    """Get latency between two events"""
    if utterance_id not in _tracking_data:
        return None
    data = _tracking_data[utterance_id]
    if start_event not in data or end_event not in data:
        return None
    return data[end_event] - data[start_event]


def cleanup(utterance_id: str):
    """Clean up tracking data for an utterance"""
    if utterance_id in _tracking_data:
        del _tracking_data[utterance_id]

