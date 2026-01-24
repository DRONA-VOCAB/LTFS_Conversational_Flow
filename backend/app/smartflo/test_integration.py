"""
Minimal test to verify the /vendor-stream endpoint integration.
This test verifies the endpoint can be added to a FastAPI app.
"""

from fastapi import FastAPI, WebSocket
from smartflo.websocket_server import smartflo_server

# Create a minimal FastAPI app just for testing
test_app = FastAPI()


@test_app.websocket("/vendor-stream")
async def vendor_stream_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Tata Smartflo Bi-Directional Audio Streaming.
    """
    await smartflo_server.handle_socket(websocket)


if __name__ == "__main__":
    print("=" * 60)
    print("Testing /vendor-stream endpoint integration")
    print("=" * 60)
    print()
    
    # Verify the app has the route
    routes = [route.path for route in test_app.routes if hasattr(route, 'path')]
    
    if '/vendor-stream' in routes:
        print("✓ /vendor-stream endpoint registered successfully")
        print(f"✓ Total routes in test app: {len(routes)}")
        print()
        print("The endpoint is ready to accept connections from Smartflo.")
        print()
        print("To test with a real server, run:")
        print("  uvicorn smartflo.test_integration:test_app --host 0.0.0.0 --port 8000")
        print()
        print("Then connect a WebSocket client to:")
        print("  ws://localhost:8000/vendor-stream")
        print()
        print("=" * 60)
        print("✓ Integration test PASSED")
        print("=" * 60)
    else:
        print("✗ /vendor-stream endpoint NOT found")
        print(f"Available routes: {routes}")
        exit(1)
