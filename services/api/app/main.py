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
from .tasks import cleanup_task
from . import __version__


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    settings = get_settings()
    
    # Startup
    print(f"Starting Cat Caption Cage Match API v{__version__}")
    print(f"  Storage Type: {settings.storage_type}")
    print(f"  LLM Provider: {settings.llm_provider}")
    print(f"  CORS Origins: {settings.cors_origins}")
    
    # Initialize database if using SQL storage
    if settings.storage_type == "sql":
        from .db.connection import init_db, close_db
        print(f"  Database URL: {settings.database_url}")
        await init_db()
        print("  Database initialized")
    
    # Configure Socket.IO CORS
    configure_cors(settings.cors_origins)
    
    # Start background cleanup task
    cleanup_task.start()
    
    yield
    
    # Shutdown
    print("Shutting down...")
    cleanup_task.stop()
    if settings.storage_type == "sql":
        from .db.connection import close_db
        await close_db()
        print("  Database connection closed")


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

