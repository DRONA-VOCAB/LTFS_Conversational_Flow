SESSIONS = {}

def get_session(session_id):
    return SESSIONS.get(session_id)

def save_session(session):
    SESSIONS[session["session_id"]] = session
