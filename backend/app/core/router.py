"""
WebSocket router for dispatching events to appropriate handlers.
"""

import logging
from typing import Callable, Dict, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class EventRouter:
    """
    Routes incoming events to appropriate handlers based on event type.
    """

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}

    def register(self, event_type: str, handler: Callable) -> None:
        """
        Register a handler for a specific event type.

        Args:
            event_type: Type of event (e.g., "start", "media", "stop")
            handler: Async handler function
        """
        self._handlers[event_type] = handler
        logger.info(
            f"✅ Registered handler for event type: {event_type} -> {handler.__name__}"
        )

    def route(self, event_type: str) -> Callable:
        """
        Decorator for registering event handlers.

        Example:
            @router.route("start")
            async def handle_start(event, websocket):
                ...

        Args:
            event_type: Type of event to handle

        Returns:
            Decorator function
        """

        def decorator(handler: Callable) -> Callable:
            self.register(event_type, handler)
            return handler

        return decorator

    async def dispatch(
        self, event: Any, websocket: WebSocket, **kwargs
    ) -> Optional[Any]:
        """
        Dispatch an event to its registered handler.

        Args:
            event: Event data (dict or Pydantic object)
            websocket: WebSocket connection
            **kwargs: Additional arguments to pass to handler

        Returns:
            Result from the handler, if any

        Raises:
            ValueError: If no handler is registered for the event type
        """
        # Support both dict and Pydantic objects
        if isinstance(event, dict):
            event_type = event.get("type") or event.get("event")
        else:
            event_type = getattr(event, "event", None) or getattr(event, "type", None)

        if not event_type or event_type not in self._handlers:
            logger.warning(f"⚠️ No handler registered for event type: {event_type}")
            logger.info(f"📋 Available handlers: {list(self._handlers.keys())}")
            raise ValueError(f"No handler for event type: {event_type}")

        handler = self._handlers[event_type]
        logger.info(f"🚀 Dispatching {event_type} event to handler: {handler.__name__}")

        try:
            result = await handler(event, websocket, **kwargs)
            logger.info(f"✅ Handler {handler.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(
                f"❌ Error in handler for {event_type}: {str(e)}", exc_info=True
            )
            raise

    def get_handler(self, event_type: str) -> Optional[Callable]:
        """
        Get the handler for a specific event type.

        Args:
            event_type: Type of event

        Returns:
            Handler function or None if not found
        """
        return self._handlers.get(event_type)

    def list_handlers(self) -> Dict[str, str]:
        """
        List all registered handlers.

        Returns:
            Dictionary of event_type -> handler_name
        """
        return {
            event_type: handler.__name__
            for event_type, handler in self._handlers.items()
        }


# Global router instance
router = EventRouter()
