# Routes package
# session_routes removed - using WebSocket with external chatbot API instead
# Keeping only customer_routes for frontend customer list
from .customer_routes import router as customer_router, sessions_router

__all__ = ["customer_router", "sessions_router"]

