"""
Middleware pipeline for event processing.
Handles validation, logging, and exception handling.
"""

import json
import logging
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class MiddlewareContext:
    """Context object passed through middleware pipeline"""

    def __init__(self, raw_message: str):
        self.raw_message = raw_message
        self.json_data: Optional[dict] = None
        self.validated_event: Optional[Any] = None
        self.error: Optional[Exception] = None
        self.metadata: dict = {}


async def json_validation_middleware(ctx: MiddlewareContext) -> MiddlewareContext:
    """
    Validate that the message is valid JSON.

    Args:
        ctx: Middleware context

    Returns:
        Updated context
    """
    try:
        ctx.json_data = json.loads(ctx.raw_message)
        logger.debug(f"JSON validation passed: {ctx.json_data.get('event', 'unknown')}")
    except json.JSONDecodeError as e:
        ctx.error = ValueError(f"Invalid JSON: {str(e)}")
        logger.error(f"JSON validation failed: {str(e)}")

    return ctx


async def logging_middleware(ctx: MiddlewareContext) -> MiddlewareContext:
    """
    Log incoming events.

    Args:
        ctx: Middleware context

    Returns:
        Updated context
    """
    if ctx.validated_event:
        # Handle both dict and Pydantic objects
        if isinstance(ctx.validated_event, dict):
            event_type = ctx.validated_event.get("type") or ctx.validated_event.get(
                "event"
            )
            logger.debug(f"Received event: {event_type}")
        else:
            event_type = getattr(ctx.validated_event, "event", None) or getattr(
                ctx.validated_event, "type", None
            )
            sequence = getattr(ctx.validated_event, "sequenceNumber", None)
            stream_sid = getattr(ctx.validated_event, "streamSid", None)
            logger.debug(
                f"Received event: {event_type} (seq: {sequence}, stream: {stream_sid})"
            )

    return ctx


async def event_validation_middleware(ctx: MiddlewareContext) -> MiddlewareContext:
    """
    Validate event structure (optional - can be extended for Pydantic validation).

    Args:
        ctx: Middleware context

    Returns:
        Updated context
    """
    # For now, just pass through - can add Pydantic validation later
    if ctx.json_data:
        ctx.validated_event = ctx.json_data
    return ctx


class MiddlewarePipeline:
    """
    Middleware pipeline for processing incoming messages.
    """

    def __init__(self):
        self.middlewares = [
            json_validation_middleware,
            event_validation_middleware,
            logging_middleware,
        ]

    async def process(self, raw_message: str) -> MiddlewareContext:
        """
        Process a raw message through the middleware pipeline.

        Args:
            raw_message: Raw message string

        Returns:
            Middleware context with validation results
        """
        ctx = MiddlewareContext(raw_message)

        for middleware in self.middlewares:
            ctx = await middleware(ctx)

            # Stop processing if there's an error
            if ctx.error:
                break

        return ctx


def exception_handler(func: Callable) -> Callable:
    """
    Decorator for automatic exception handling in handlers.

    Args:
        func: Handler function to wrap

    Returns:
        Wrapped function
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(
                f"Exception in handler {func.__name__}: {str(e)}", exc_info=True
            )
            raise

    return wrapper
