# Services package
from .summary_service import (
    generate_human_summary,
    generate_fallback_summary,
    get_closing_statement,
    is_survey_completed,
    transliterate_to_devanagari,
    detect_confirmation,
    detect_field_to_edit,
    get_edit_prompt,
)

__all__ = [
    "generate_human_summary",
    "generate_fallback_summary",
    "get_closing_statement",
    "is_survey_completed",
    "transliterate_to_devanagari",
    "detect_confirmation",
    "detect_field_to_edit",
    "get_edit_prompt",
]


import os
import logging

# Choose between 'silero' or 'webrtc'
VAD_BACKEND = os.getenv("VAD_BACKEND", "silero").lower()

logger = logging.getLogger(__name__)
from .vad_silero import process_frame, cleanup_connection, connections
