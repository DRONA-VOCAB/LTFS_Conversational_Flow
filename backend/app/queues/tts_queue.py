import asyncio

# This queue holds the generated text responses from the LLM service.
# Each item in the queue is a tuple: (websocket, text)
# - websocket: The WebSocket connection object for the client.
# - text: The string of text to be converted to speech.
tts_queue = asyncio.Queue()