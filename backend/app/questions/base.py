class QuestionResult:
    def __init__(self, is_clear: bool, value=None, extra=None):
        self.is_clear = is_clear
        self.value = value
        self.extra = extra or {}
