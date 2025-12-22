"""
Socket.IO manager for realtime events.

Handles WebSocket connections and broadcasts game events to connected clients.
"""
import socketio
from typing import Optional

from .config import get_settings
from .dependencies import get_storage
from .services.tokens import verify_player_token


# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[],  # Will be set on app startup
    logger=True,
    engineio_logger=False,
)

# Track connected players: sid -> {session_code, player_id}
_connected_players: dict[str, dict] = {}


def configure_cors(origins: list[str]) -> None:
    """Configure CORS for Socket.IO."""
    sio.eio.cors_allowed_origins = origins


# ============================================================================
# Connection Events
# ============================================================================


@sio.event
async def connect(sid: str, environ: dict, auth: Optional[dict] = None):
    """Handle client connection."""
    print(f"Client connected: {sid}")
    # Auth will be handled on session:join


@sio.event
async def disconnect(sid: str):
    """Handle client disconnection."""
    player_info = _connected_players.pop(sid, None)
    if player_info:
        print(f"Player disconnected: {player_info}")
        # Could broadcast player_left event here


# ============================================================================
# Client -> Server Events
# ============================================================================


@sio.on("session:join")
async def session_join(sid: str, data: dict):
    """
    Client joins a session room.
    
    Payload: { "sessionCode": "K9Q2TZ", "playerToken": "..." }
    Ack: { "ok": true, "state": {...} } or { "ok": false, "error": "..." }
    """
    session_code = data.get("sessionCode", "").upper()
    player_token = data.get("playerToken", "")
    
    if not session_code:
        return {"ok": False, "error": "Session code required"}
    
    # Verify token if provided
    player_id = None
    if player_token:
        player_id = verify_player_token(player_token, session_code)
    
    # Join the session room
    room = f"session:{session_code}"
    await sio.enter_room(sid, room)
    
    # Track connection
    _connected_players[sid] = {
        "session_code": session_code,
        "player_id": player_id,
    }
    
    # Get current state
    storage = get_storage()
    session = await storage.get_session(session_code)
    
    if not session:
        return {"ok": False, "error": f"Session '{session_code}' not found"}
    
    players = await storage.get_players(session_code)
    current_round = await storage.get_current_round(session_code)
    leaderboard = await storage.get_leaderboard(session_code)
    
    return {
        "ok": True,
        "state": {
            "session": session.model_dump(mode="json"),
            "players": [p.model_dump(mode="json") for p in players],
            "currentRound": current_round.model_dump(mode="json") if current_round else None,
            "leaderboard": [e.model_dump(mode="json") for e in leaderboard],
        },
    }


@sio.on("host:start_round")
async def host_start_round(sid: str, data: dict):
    """
    Host starts a new round.
    
    Payload: { "sessionCode": "K9Q2TZ" }
    """
    # This is handled via REST API, but we could add Socket.IO version
    return {"ok": False, "error": "Use REST API for this action"}


@sio.on("player:submit_caption")
async def player_submit_caption(sid: str, data: dict):
    """
    Player submits a caption.
    
    Payload: { "sessionCode": "K9Q2TZ", "roundId": "...", "text": "..." }
    """
    # This is handled via REST API, but we could add Socket.IO version
    return {"ok": False, "error": "Use REST API for this action"}


@sio.event
async def ping(sid: str, data: dict):
    """
    Client ping for time sync.
    
    Payload: { "t": 123 }
    Ack: { "t": 123, "serverTime": "..." }
    """
    from datetime import datetime, timezone
    
    return {
        "t": data.get("t"),
        "serverTime": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# Server -> Client Broadcasts
# ============================================================================


async def broadcast_session_state(session_code: str) -> None:
    """Broadcast updated session state to all clients in the room."""
    storage = get_storage()
    
    session = await storage.get_session(session_code)
    if not session:
        return
    
    players = await storage.get_players(session_code)
    current_round = await storage.get_current_round(session_code)
    leaderboard = await storage.get_leaderboard(session_code)
    
    room = f"session:{session_code}"
    await sio.emit(
        "session:state",
        {
            "session": session.model_dump(mode="json"),
            "players": [p.model_dump(mode="json") for p in players],
            "currentRound": current_round.model_dump(mode="json") if current_round else None,
            "leaderboard": [e.model_dump(mode="json") for e in leaderboard],
        },
        room=room,
    )


async def broadcast_round_started(session_code: str, round_data: dict) -> None:
    """Broadcast that a new round has started."""
    room = f"session:{session_code}"
    await sio.emit("round:started", {"round": round_data}, room=room)


async def broadcast_caption_locked(
    session_code: str, round_id: str, player_id: str
) -> None:
    """Broadcast that a player has submitted their caption."""
    room = f"session:{session_code}"
    await sio.emit(
        "caption:locked",
        {"roundId": round_id, "playerId": player_id, "submitted": True},
        room=room,
    )


async def broadcast_round_revealed(
    session_code: str, round_data: dict, captions: list, leaderboard: list
) -> None:
    """Broadcast round results."""
    room = f"session:{session_code}"
    await sio.emit(
        "round:revealed",
        {
            "round": round_data,
            "captions": captions,
            "leaderboard": leaderboard,
        },
        room=room,
    )


async def broadcast_error(session_code: str, code: str, message: str) -> None:
    """Broadcast an error to all clients in a session."""
    room = f"session:{session_code}"
    await sio.emit("error", {"code": code, "message": message}, room=room)

