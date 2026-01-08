import json
import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# The file where all latency reports are stored
LATENCY_FILE_PATH = "latency_records.json"


def load_records() -> List[Dict[str, Any]]:
    """Loads all latency records from the JSON file."""
    if not os.path.exists(LATENCY_FILE_PATH):
        logger.warning(f"Latency file not found: {LATENCY_FILE_PATH}. Returning empty list.")
        return []
    try:
        with open(LATENCY_FILE_PATH, 'r') as f:
            # Load the entire list of records
            records = json.load(f)
            logger.debug(f"Successfully loaded {len(records)} records.")
            return records
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load latency records from {LATENCY_FILE_PATH}: {e}")
        # Return empty list on read error so the application doesn't crash
        return []


def save_record(new_record: Dict[str, Any]):
    """
    Appends a new record to the list and saves the entire list back to the JSON file.
    """
    records = load_records()
    records.append(new_record)

    try:
        # Overwrite the file with the updated list
        with open(LATENCY_FILE_PATH, 'w') as f:
            # Use indent=4 for human readability
            json.dump(records, f, indent=4)
        logger.info(f"💾 Saved 1 new latency record to {LATENCY_FILE_PATH}. Total records: {len(records)}")
    except IOError as e:
        logger.error(f"Failed to save latency records to {LATENCY_FILE_PATH}: {e}")