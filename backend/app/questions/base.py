# class QuestionResult:
#     def __init__(self, is_clear: bool, value=None, extra=None):
#         self.is_clear = is_clear
#         self.value = value
#         self.extra = extra or {}


class QuestionResult:
    def __init__(self, is_clear: bool, value=None, extra=None, response_text=None):
        self.is_clear = is_clear
        self.value = value
        self.extra = extra or {}
        self.response_text = response_text  # For acknowledgment/clarification responses
