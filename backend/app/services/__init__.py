import os
import logging

# Choose between 'silero' or 'webrtc'
VAD_BACKEND = os.getenv("VAD_BACKEND", "silero").lower()

logger = logging.getLogger(__name__)
from .vad_silero import process_frame, cleanup_connection, connections
