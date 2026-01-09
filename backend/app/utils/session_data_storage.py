"""Utility for storing session data in files"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Get the app directory (where this file is located)
APP_DIR = Path(__file__).parent.parent
# Create session_data directory relative to app directory
SESSION_DATA_DIR = APP_DIR / "session_data"
SESSION_DATA_DIR.mkdir(exist_ok=True)


def save_db_data(session_id: str, db_data: Dict[str, Any]) -> bool:
    """
    Save database-fetched data to session file.
    
    Args:
        session_id: Unique session identifier
        db_data: Dictionary containing all database fields
    
    Returns:
        True if successful, False otherwise
    """
    try:
        file_path = SESSION_DATA_DIR / f"{session_id}.json"
        
        # Load existing data if file exists, otherwise create new structure
        existing_data = {}
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load existing file {file_path}, creating new: {e}")
                existing_data = {}
        
        # Update or set db_data (preserve session_data if it exists)
        existing_data["db_data"] = db_data
        
        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"💾 Saved DB data for session: {session_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Error saving DB data for session {session_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def save_session_data(session_id: str, session: Dict[str, Any]) -> bool:
    """
    Save session data (collected during call) to session file.
    Excludes internal fields like current_question, retry_count.
    
    Args:
        session_id: Unique session identifier
        session: Dictionary containing session data
    
    Returns:
        True if successful, False otherwise
    """
    try:
        file_path = SESSION_DATA_DIR / f"{session_id}.json"
        
        # Load existing data if file exists (to preserve db_data)
        existing_data = {}
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load existing file {file_path}, creating new: {e}")
                existing_data = {}
        
        # Prepare session data (exclude internal fields)
        session_data = {
            k: v
            for k, v in session.items()
            if v is not None and k not in [
                "current_question",
                "retry_count",
            ]
        }
        
        # Update or set session_data (preserve db_data if it exists)
        existing_data["session_data"] = session_data
        
        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"💾 Saved session data for session: {session_id} (fields: {len(session_data)})")
        return True
    except Exception as e:
        logger.error(f"❌ Error saving session data for session {session_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def load_session_file(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Load session file data.
    
    Args:
        session_id: Unique session identifier
    
    Returns:
        Dictionary with db_data and session_data, or None if file doesn't exist
    """
    try:
        file_path = SESSION_DATA_DIR / f"{session_id}.json"
        if not file_path.exists():
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Error loading session file {session_id}: {e}")
        return None