"""Custom exceptions for the application."""


class TTSServiceError(Exception):
    """Exception raised when TTS service fails."""
    
    def __init__(self, message: str, service_url: str = None):
        self.message = message
        self.service_url = service_url
        super().__init__(self.message)
    
    def __str__(self):
        error_msg = self.message
        if self.service_url:
            error_msg += f" (TTS service: {self.service_url})"
        error_msg += ". Consider using the text-based endpoint /api/v1/conversation/text/initiate if TTS is unavailable."
        return error_msg


class ASRServiceError(Exception):
    """Exception raised when ASR service fails."""
    
    def __init__(self, message: str, service_url: str = None):
        self.message = message
        self.service_url = service_url
        super().__init__(self.message)
    
    def __str__(self):
        error_msg = self.message
        if self.service_url:
            error_msg += f" (ASR service: {self.service_url})"
        return error_msg

