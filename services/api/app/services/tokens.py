"""
Player token generation and verification.

Uses HMAC-SHA256 for simple, stateless token signing.
Tokens are not JWTs - just signed payloads for lightweight auth.
"""
import hmac
import hashlib
import base64
import time
from typing import Optional

from ..config import get_settings


# Token expiry: 24 hours
TOKEN_EXPIRY_SECONDS = 24 * 60 * 60


def create_player_token(player_id: str, session_code: str) -> str:
    """
    Create a signed token for a player.
    
    Token format: base64(player_id:session_code:timestamp:signature)
    """
    settings = get_settings()
    timestamp = str(int(time.time()))
    
    # Create payload
    payload = f"{player_id}:{session_code}:{timestamp}"
    
    # Sign with HMAC-SHA256
    signature = hmac.new(
        settings.app_secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()[:16]  # Truncate for shorter tokens
    
    # Encode
    token_data = f"{payload}:{signature}"
    return base64.urlsafe_b64encode(token_data.encode()).decode()


def verify_player_token(token: str, expected_session_code: str) -> Optional[str]:
    """
    Verify a player token and return the player_id if valid.
    
    Returns None if:
    - Token is malformed
    - Signature is invalid
    - Token is expired
    - Session code doesn't match
    """
    settings = get_settings()
    
    try:
        # Decode
        token_data = base64.urlsafe_b64decode(token.encode()).decode()
        parts = token_data.split(":")
        
        if len(parts) != 4:
            return None
        
        player_id, session_code, timestamp, provided_signature = parts
        
        # Check session code matches
        if session_code.upper() != expected_session_code.upper():
            return None
        
        # Check expiry
        token_time = int(timestamp)
        if time.time() - token_time > TOKEN_EXPIRY_SECONDS:
            return None
        
        # Verify signature
        payload = f"{player_id}:{session_code}:{timestamp}"
        expected_signature = hmac.new(
            settings.app_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()[:16]
        
        if not hmac.compare_digest(provided_signature, expected_signature):
            return None
        
        return player_id
        
    except Exception:
        return None

