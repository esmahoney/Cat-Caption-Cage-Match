"""
Cat Caption Cage Match - FastAPI Backend

Main application entry point with REST API and Socket.IO.
"""
import socketio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import health_router, sessions_router
from .socket_manager import sio, configure_cors
from . import __version__


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    settings = get_settings()
    
    # Startup
    print(f"Starting Cat Caption Cage Match API v{__version__}")
    print(f"  LLM Provider: {settings.llm_provider}")
    print(f"  CORS Origins: {settings.cors_origins}")
    
    # Configure Socket.IO CORS
    configure_cors(settings.cors_origins)
    
    yield
    
    # Shutdown
    print("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Cat Caption Cage Match API",
    description="Backend API for the AI-powered cat caption party game",
    version=__version__,
    lifespan=lifespan,
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")


# Mount Socket.IO
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Cat Caption Cage Match API",
        "version": __version__,
        "docs": "/docs",
        "health": "/api/health",
    }


# Create the combined ASGI app
def create_app() -> socketio.ASGIApp:
    """Create the combined FastAPI + Socket.IO ASGI app."""
    return socket_app


# For running with uvicorn directly
combined_app = create_app()

