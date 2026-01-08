import asyncio

# This queue holds the transcribed text from the ASR service.
# Each item in the queue is a tuple: (websocket, text)
# - websocket: The WebSocket connection object for the client.
# - text: The string of recognized text.
llm_queue = asyncio.Queue()