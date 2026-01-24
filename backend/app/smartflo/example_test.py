"""
Example test client for Tata Smartflo WebSocket integration.
This demonstrates how to test the vendor WebSocket server.
"""

import asyncio
import json
import websockets
import base64
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_smartflo_integration():
    """
    Test the Smartflo WebSocket server with example messages.
    """
    # Connect to the vendor stream endpoint
    uri = "ws://localhost:8000/vendor-stream"
    
    logger.info(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("Connected successfully!")
            
            # 1. Receive the connected event
            connected_response = await websocket.recv()
            logger.info(f"Received connected event: {connected_response}")
            connected_data = json.loads(connected_response)
            assert connected_data["event"] == "connected"
            
            # 2. Send start event
            logger.info("Sending start event...")
            start_event = {
                "event": "start",
                "sequenceNumber": "1",
                "streamSid": "ST_DEMO_123456",
                "start": {
                    "callSid": "CA_DEMO_123456",
                    "streamSid": "ST_DEMO_123456",
                    "accountSid": "AC_DEMO_123456",
                    "tracks": "inbound",
                    "customParameters": {
                        "test": "demo"
                    },
                    "mediaFormat": {
                        "encoding": "audio/x-mulaw",
                        "sampleRate": 8000,
                        "channels": 1
                    }
                }
            }
            await websocket.send(json.dumps(start_event))
            await asyncio.sleep(0.5)
            
            # 3. Send multiple media events with sample audio
            logger.info("Sending media events...")
            
            # Create some dummy μ-law audio data (just for testing)
            # In production, this would be real audio from Smartflo
            dummy_audio = bytes([0x00, 0x01, 0x02, 0x03, 0x04, 0x05] * 100)
            base64_audio = base64.b64encode(dummy_audio).decode('utf-8')
            
            for i in range(5):
                media_event = {
                    "event": "media",
                    "sequenceNumber": str(2 + i),
                    "streamSid": "ST_DEMO_123456",
                    "media": {
                        "payload": base64_audio,
                        "chunk": str(i + 1),
                        "timestamp": str(1234567890 + i * 20)
                    }
                }
                await websocket.send(json.dumps(media_event))
                logger.info(f"Sent media event {i + 1}/5")
                await asyncio.sleep(0.1)
            
            # 4. Send DTMF event
            logger.info("Sending DTMF event...")
            dtmf_event = {
                "event": "dtmf",
                "sequenceNumber": "7",
                "streamSid": "ST_DEMO_123456",
                "dtmf": {
                    "callSid": "CA_DEMO_123456",
                    "streamSid": "ST_DEMO_123456",
                    "digit": "1",
                    "track": "inbound"
                }
            }
            await websocket.send(json.dumps(dtmf_event))
            await asyncio.sleep(0.5)
            
            # 5. Send mark event
            logger.info("Sending mark event...")
            mark_event = {
                "event": "mark",
                "sequenceNumber": "8",
                "streamSid": "ST_DEMO_123456",
                "mark": {
                    "name": "test_mark_1"
                }
            }
            await websocket.send(json.dumps(mark_event))
            await asyncio.sleep(0.5)
            
            # 6. Send stop event
            logger.info("Sending stop event...")
            stop_event = {
                "event": "stop",
                "sequenceNumber": "9",
                "streamSid": "ST_DEMO_123456",
                "stop": {
                    "callSid": "CA_DEMO_123456",
                    "streamSid": "ST_DEMO_123456",
                    "accountSid": "AC_DEMO_123456"
                }
            }
            await websocket.send(json.dumps(stop_event))
            await asyncio.sleep(0.5)
            
            logger.info("Test completed successfully!")
            
    except websockets.exceptions.WebSocketException as e:
        logger.error(f"WebSocket error: {e}")
    except ConnectionRefusedError:
        logger.error("Connection refused. Is the server running?")
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)


async def test_multiple_sessions():
    """
    Test multiple concurrent sessions.
    """
    logger.info("Testing multiple concurrent sessions...")
    
    async def create_session(session_id: int):
        uri = "ws://localhost:8000/vendor-stream"
        stream_sid = f"ST_MULTI_{session_id}"
        call_sid = f"CA_MULTI_{session_id}"
        
        try:
            async with websockets.connect(uri) as websocket:
                # Receive connected
                await websocket.recv()
                
                # Send start
                start_event = {
                    "event": "start",
                    "sequenceNumber": "1",
                    "streamSid": stream_sid,
                    "start": {
                        "callSid": call_sid,
                        "streamSid": stream_sid
                    }
                }
                await websocket.send(json.dumps(start_event))
                await asyncio.sleep(0.5)
                
                # Send media
                dummy_audio = bytes([0x00] * 100)
                base64_audio = base64.b64encode(dummy_audio).decode('utf-8')
                
                media_event = {
                    "event": "media",
                    "sequenceNumber": "2",
                    "streamSid": stream_sid,
                    "media": {
                        "payload": base64_audio,
                        "chunk": "1",
                        "timestamp": "1234567890"
                    }
                }
                await websocket.send(json.dumps(media_event))
                await asyncio.sleep(0.5)
                
                # Send stop
                stop_event = {
                    "event": "stop",
                    "sequenceNumber": "3",
                    "streamSid": stream_sid,
                    "stop": {
                        "callSid": call_sid,
                        "streamSid": stream_sid
                    }
                }
                await websocket.send(json.dumps(stop_event))
                
                logger.info(f"Session {session_id} completed")
        except Exception as e:
            logger.error(f"Session {session_id} failed: {e}")
    
    # Create 3 concurrent sessions
    await asyncio.gather(
        create_session(1),
        create_session(2),
        create_session(3)
    )
    
    logger.info("Multiple sessions test completed!")


async def test_error_handling():
    """
    Test error handling with invalid messages.
    """
    logger.info("Testing error handling...")
    
    uri = "ws://localhost:8000/vendor-stream"
    
    try:
        async with websockets.connect(uri) as websocket:
            # Receive connected
            await websocket.recv()
            
            # Send invalid JSON
            logger.info("Sending invalid JSON...")
            await websocket.send("invalid json {{{")
            await asyncio.sleep(0.5)
            
            # Send valid JSON but invalid event
            logger.info("Sending invalid event type...")
            invalid_event = {
                "event": "unknown_event_type",
                "sequenceNumber": "1",
                "streamSid": "ST_ERROR_TEST"
            }
            await websocket.send(json.dumps(invalid_event))
            await asyncio.sleep(0.5)
            
            # Send event with missing required fields
            logger.info("Sending event with missing fields...")
            incomplete_event = {
                "event": "start",
                "sequenceNumber": "1"
                # Missing streamSid and start data
            }
            await websocket.send(json.dumps(incomplete_event))
            await asyncio.sleep(0.5)
            
            logger.info("Error handling test completed (check server logs)")
            
    except Exception as e:
        logger.error(f"Error test failed: {e}")


def main():
    """
    Main test runner.
    """
    print("=" * 60)
    print("Tata Smartflo WebSocket Integration Test Suite")
    print("=" * 60)
    print()
    print("Make sure the server is running:")
    print("  uvicorn main:app --host 0.0.0.0 --port 8000")
    print()
    print("=" * 60)
    print()
    
    # Run tests
    logger.info("Starting test suite...")
    
    try:
        # Test 1: Basic integration test
        logger.info("\n" + "=" * 60)
        logger.info("TEST 1: Basic Integration Test")
        logger.info("=" * 60)
        asyncio.run(test_smartflo_integration())
        
        # Test 2: Multiple concurrent sessions
        logger.info("\n" + "=" * 60)
        logger.info("TEST 2: Multiple Concurrent Sessions")
        logger.info("=" * 60)
        asyncio.run(test_multiple_sessions())
        
        # Test 3: Error handling
        logger.info("\n" + "=" * 60)
        logger.info("TEST 3: Error Handling")
        logger.info("=" * 60)
        asyncio.run(test_error_handling())
        
        logger.info("\n" + "=" * 60)
        logger.info("ALL TESTS COMPLETED")
        logger.info("=" * 60)
        
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)


if __name__ == "__main__":
    main()
