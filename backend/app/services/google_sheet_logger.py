import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional

import gspread
from google.oauth2.service_account import Credentials

from config.settings import GOOGLE_SHEET_ID

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDS_PATH = Path(__file__).resolve().parents[2] / "google_sheet_creds.json"
_creds_missing_logged = False


def _get_client() -> Optional[gspread.Client]:
    """Create an authenticated gspread client, or None if creds file is missing."""
    global _creds_missing_logged
    if not CREDS_PATH.exists():
        if not _creds_missing_logged:
            logger.warning(
                "Google Sheet creds not found at %s - sheet logging disabled",
                CREDS_PATH,
            )
            _creds_missing_logged = True
        return None
    creds = Credentials.from_service_account_file(str(CREDS_PATH), scopes=SCOPES)
    return gspread.authorize(creds)


def _append_row(row_data: Dict[str, str]) -> Optional[int]:
    """Append a row to the configured Google Sheet, or None if disabled."""
    client = _get_client()
    if client is None:
        return None
    sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
    current_rows = len(sheet.get_all_values())
    row_number = current_rows + 1

    sheet.append_row(
        [
            row_number,
            row_data.get("session_id", ""),
            row_data.get("asr_audio_url", ""),
            row_data.get("transcription", ""),
            row_data.get("llm_response", ""),
            row_data.get("tts_audio_url", ""),
        ],
        value_input_option="USER_ENTERED",
    )
    return row_number


async def log_interaction(row_data: Dict[str, str]) -> Optional[int]:
    """Append interaction data to Google Sheet asynchronously."""
    try:
        return await asyncio.to_thread(_append_row, row_data)
    except Exception as exc:  # pragma: no cover - logging only
        logger.error("Failed to append row to Google Sheet: %s", exc, exc_info=True)
        return None
