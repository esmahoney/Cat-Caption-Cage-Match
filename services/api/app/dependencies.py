"""
FastAPI dependencies for dependency injection.
"""
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, Path, status

from .storage import Storage, InMemoryStorage
from .config import get_settings, Settings
from .services.tokens import verify_player_token


# Global storage instance (will be set on app startup)
_storage: Optional[Storage] = None


def get_storage() -> Storage:
    """Get the storage instance."""
    global _storage
    if _storage is None:
        # Default to in-memory storage for development
        settings = get_settings()
        _storage = InMemoryStorage(session_expiry_hours=settings.session_expiry_hours)
    return _storage


def set_storage(storage: Storage) -> None:
    """Set the storage instance (for testing or switching implementations)."""
    global _storage
    _storage = storage


async def get_current_player_id(
    authorization: Annotated[Optional[str], Header()] = None,
    session_code: str = Path(...),
) -> str:
    """
    Extract and verify player ID from Authorization header.
    
    Expected format: Bearer <player_token>
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Authorization header required"},
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid authorization format"},
        )
    
    token = authorization[7:]  # Remove "Bearer " prefix
    player_id = verify_player_token(token, session_code.upper())
    
    if not player_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid or expired token"},
        )
    
    return player_id


async def require_host(
    player_id: Annotated[str, Depends(get_current_player_id)],
    session_code: str = Path(...),
    storage: Storage = Depends(get_storage),
) -> str:
    """
    Verify the current player is the host of the session.
    Returns the player_id if authorized.
    """
    is_host = await storage.is_host(session_code.upper(), player_id)
    
    if not is_host:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "UNAUTHORIZED", "message": "Host access required"},
        )
    
    return player_id

