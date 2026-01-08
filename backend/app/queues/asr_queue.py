import asyncio

# This queue holds incoming audio chunks from the client's microphone.
# Each item in the queue is a tuple: (websocket, audio_data)
# - websocket: The WebSocket connection object for the client.
# - audio_data: The binary audio chunk.
asr_queue = asyncio.Queue()