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

# Determine availability once to avoid repeated noisy errors at runtime
SHEETS_AVAILABLE = CREDS_PATH.exists() and bool(GOOGLE_SHEET_ID)
if not SHEETS_AVAILABLE:
    logger.info(
        "Google Sheets logging disabled: missing credentials or GOOGLE_SHEET_ID."
        f" CREDS_PATH={CREDS_PATH} GOOGLE_SHEET_ID={GOOGLE_SHEET_ID}"
    )


def _get_client() -> gspread.Client:
    """Create an authenticated gspread client."""
    creds = Credentials.from_service_account_file(str(CREDS_PATH), scopes=SCOPES)
    return gspread.authorize(creds)


def _append_row(row_data: Dict[str, str]) -> int:
    """Append a row to the configured Google Sheet."""
    client = _get_client()
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
    if not SHEETS_AVAILABLE:
        return None

    try:
        return await asyncio.to_thread(_append_row, row_data)
    except Exception as exc:  # pragma: no cover - logging only
        logger.error("Failed to append row to Google Sheet: %s", exc, exc_info=True)
        return None
