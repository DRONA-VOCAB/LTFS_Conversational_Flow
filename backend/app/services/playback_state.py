import uuid


class PlaybackState:
    def __init__(self):
        self.token = None

    def new_token(self):
        self.token = uuid.uuid4().hex
        return self.token

    def cancel(self):
        self.token = None

    def is_valid(self, token):
        return self.token == token


playback_states = {}


def get_playback_state(ws):
    return playback_states.setdefault(ws, PlaybackState())


def cleanup_playback(ws):
    playback_states.pop(ws, None)
