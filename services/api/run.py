#!/usr/bin/env python3
"""
Development server runner for Cat Caption Cage Match API.

Usage:
    python run.py
    
Or with uvicorn directly:
    uvicorn app.main:combined_app --reload --host 0.0.0.0 --port 8000
"""
import os
import sys

# Add the services/api directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main():
    import uvicorn
    
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    reload = os.environ.get("DEBUG", "false").lower() == "true"
    
    print(f"Starting server on http://{host}:{port}")
    print(f"  API docs: http://localhost:{port}/docs")
    print(f"  Health check: http://localhost:{port}/api/health")
    print()
    
    uvicorn.run(
        "app.main:combined_app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()

