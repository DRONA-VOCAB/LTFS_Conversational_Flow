# """FastAPI application entry point"""

# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from fastapi import APIRouter, HTTPException

# from routes import session_router

# app = FastAPI(
#     title="L and T Finance Customer Survey API",
#     description="API for managing customer survey sessions",
#     version="1.0.0",
# )

# # CORS (can be restricted later)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # -------------------------
# # API ROUTES
# # -------------------------
# router = APIRouter(prefix="/sessions", tags=["sessions"])

# # -------------------------
# # FRONTEND (React build)
# # -------------------------
# app.mount(
#     "/", 
#     StaticFiles(directory="static", html=True),
#     name="frontend"
# )

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8001)


"""FastAPI application entry point"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import session_router

# Create FastAPI app
app = FastAPI(
    title="L and T Finance Customer Survey API",
    description="API for managing customer survey sessions",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(session_router)


# Mount frontend static files
from fastapi.staticfiles import StaticFiles
app.mount(
    "/", 
    StaticFiles(directory="static", html=True),
    name="frontend"
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
