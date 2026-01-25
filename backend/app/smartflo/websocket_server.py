"""
WebSocket server for Tata Smartflo Bi-Directional Audio Streaming.
Handles the vendor side of the WebSocket connection.
"""

import json
import logging
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from .core.middleware import MiddlewarePipeline
from .core.router import router
from .handlers.connect_handler import handle_connect
from .handlers.dtmf_handler import handle_dtmf
from .handlers.mark_handler import handle_mark
from .handlers.media_handler import handle_media
from .handlers.start_handler import handle_start
from .handlers.stop_handler import handle_stop
from .schemas.outgoing import EventBuilder

logger = logging.getLogger(__name__)


class SmartfloWebSocketServer:
    """
    WebSocket server for handling Smartflo connections.
    Manages the complete lifecycle of a Smartflo stream.
    """
    
    def __init__(self):
        self.middleware = MiddlewarePipeline()
        self._setup_routes()
    
    def _setup_routes(self):
        """Register all event handlers with the router"""
        router.register("connected", handle_connect)
        router.register("start", handle_start)
        router.register("media", handle_media)
        router.register("stop", handle_stop)
        router.register("dtmf", handle_dtmf)
        router.register("mark", handle_mark)
        
        logger.info("Event handlers registered")
        logger.debug(f"Registered handlers: {router.list_handlers()}")
    
    async def send_event(self, websocket: WebSocket, event_dict: dict) -> None:
        """
        Send an event to Smartflo.
        
        Args:
            websocket: WebSocket connection
            event_dict: Event dictionary to send
        """
        try:
            message = json.dumps(event_dict)
            await websocket.send_text(message)
            logger.debug(f"Sent event: {event_dict.get('event', 'unknown')}")
        except Exception as e:
            logger.error(f"Error sending event: {str(e)}", exc_info=True)
            raise
    
    async def send_connected_event(self, websocket: WebSocket) -> None:
        """
        Send the 'connected' event immediately after connection.
        
        Args:
            websocket: WebSocket connection
        """
        connected_event = (EventBuilder()
                          .type("connected")
                          .payload(protocol="Call", version="1.0.0")
                          .build())
        
        await self.send_event(websocket, connected_event)
        logger.info("Sent connected event to Smartflo")
    
    async def send_media_event(
        self,
        websocket: WebSocket,
        stream_sid: str,
        sequence_number: int,
        payload: str,
        chunk: Optional[str] = None,
        timestamp: Optional[str] = None
    ) -> None:
        """
        Send a media event with audio to Smartflo.
        
        Args:
            websocket: WebSocket connection
            stream_sid: Stream session identifier
            sequence_number: Sequence number
            payload: Base64 encoded μ-law audio
            chunk: Optional chunk identifier
            timestamp: Optional timestamp
        """
        media_event = (EventBuilder()
                      .type("media")
                      .sid(stream_sid)
                      .sequence(sequence_number)
                      .payload(payload=payload, chunk=chunk, timestamp=timestamp)
                      .build())
        
        await self.send_event(websocket, media_event)
        logger.debug(f"Sent media event (seq: {sequence_number}, stream_id: {stream_sid})")
    
    async def send_mark_event(
        self,
        websocket: WebSocket,
        stream_sid: str,
        sequence_number: int,
        mark_name: str
    ) -> None:
        """
        Send a mark event to Smartflo.
        
        Args:
            websocket: WebSocket connection
            stream_sid: Stream session identifier
            sequence_number: Sequence number
            mark_name: Mark identifier
        """
        mark_event = (EventBuilder()
                     .type("mark")
                     .sid(stream_sid)
                     .sequence(sequence_number)
                     .payload(name=mark_name)
                     .build())
        
        await self.send_event(websocket, mark_event)
        logger.debug(f"Sent mark event: {mark_name} (stream: {stream_sid})")
    
    async def send_clear_event(self, websocket: WebSocket, stream_sid: str) -> None:
        """
        Send a clear event to reset Smartflo's audio buffer.
        
        Args:
            websocket: WebSocket connection
            stream_sid: Stream session identifier
        """
        if stream_sid:
            clear_event = (EventBuilder()
                          .type("clear")
                          .sid(stream_sid)
                          .build())

            await self.send_event(websocket, clear_event)
            logger.debug(f"Sent clear event (stream: {stream_sid})")
        else:
            logger.warning("No stream_sid available to send clear event")
    
    async def handle_socket(self, websocket: WebSocket) -> None:
        """
        Handle a WebSocket connection from Smartflo.
        
        Main entry point for WebSocket connections.
        
        Args:
            websocket: WebSocket connection from Smartflo
        """
        await websocket.accept()
        logger.info(f"WebSocket connection accepted from {websocket.client}")
        
        try:
            # Main message loop
            while True:
                try:
                    # Receive message from Smartflo
                    raw_message = await websocket.receive_text()
                    logger.debug(f"Received message: {raw_message[:100]}...")
                    
                    # Process through middleware pipeline
                    ctx = await self.middleware.process(raw_message)
                    
                    # Check for errors
                    if ctx.error:
                        logger.error(f"Middleware error: {ctx.error}")
                        continue
                    
                    # Dispatch to appropriate handler
                    if ctx.validated_event:
                        try:
                            await router.dispatch(
                                ctx.validated_event,
                                websocket,
                                server=self
                            )
                        except Exception as e:
                            logger.error(f"Handler error: {str(e)}", exc_info=True)
                    
                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected by client")
                    break
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}", exc_info=True)
                    # Continue processing other messages
                    continue
        
        except Exception as e:
            logger.error(f"Fatal error in WebSocket handler: {str(e)}", exc_info=True)
        
        finally:
            logger.info("Closing WebSocket connection")
            # Note: Session cleanup will happen in stop_handler
            # But we can do additional cleanup here if needed


# Global server instance
smartflo_server = SmartfloWebSocketServer()
