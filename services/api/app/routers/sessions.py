"""
Session, player, round, and caption API endpoints.

This router handles all game-related REST operations.
"""
import random
import string
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Header, status

from ..models import (
    CreateSessionRequest,
    CreateSessionResponse,
    JoinSessionRequest,
    JoinSessionResponse,
    SessionStateResponse,
    StartRoundRequest,
    StartRoundResponse,
    SubmitCaptionRequest,
    SubmitCaptionResponse,
    RevealRoundResponse,
    PlayerCredentials,
    ErrorResponse,
    Score,
)
from ..storage import Storage
from ..dependencies import get_storage, get_current_player_id, require_host
from ..services.tokens import create_player_token
from ..services.images import fetch_random_cat_url
from ..services.llm import score_captions
from ..socket_manager import (
    broadcast_session_state,
    broadcast_round_started,
    broadcast_caption_locked,
    broadcast_round_revealed,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


def generate_session_code() -> str:
    """Generate a 6-character alphanumeric session code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
    random_part = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}{timestamp}_{random_part}"


# ============================================================================
# Session Endpoints
# ============================================================================


@router.post(
    "",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}},
)
async def create_session(
    request: CreateSessionRequest,
    storage: Annotated[Storage, Depends(get_storage)],
) -> CreateSessionResponse:
    """Create a new game session. The creator becomes the host."""
    
    # Generate unique session code
    session_code = generate_session_code()
    while await storage.session_exists(session_code):
        session_code = generate_session_code()
    
    # Generate host player ID and token
    host_player_id = generate_id("player_")
    host_token = create_player_token(host_player_id, session_code)
    
    # Create session
    session = await storage.create_session(
        session_code=session_code,
        host_player_id=host_player_id,
        host_display_name=request.host_display_name,
        settings=request.settings,
    )
    
    return CreateSessionResponse(
        session=session,
        host=PlayerCredentials(player_id=host_player_id, player_token=host_token),
    )


@router.get(
    "/{session_code}",
    response_model=SessionStateResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_session_state(
    session_code: str,
    storage: Annotated[Storage, Depends(get_storage)],
) -> SessionStateResponse:
    """Get the current state of a session."""
    session_code = session_code.upper()
    
    session = await storage.get_session(session_code)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Session '{session_code}' not found"},
        )
    
    players = await storage.get_players(session_code)
    current_round = await storage.get_current_round(session_code)
    leaderboard = await storage.get_leaderboard(session_code)
    
    return SessionStateResponse(
        session=session,
        players=players,
        current_round=current_round,
        leaderboard=leaderboard,
    )


@router.post(
    "/{session_code}/end",
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def end_session(
    session_code: str,
    storage: Annotated[Storage, Depends(get_storage)],
    _: Annotated[str, Depends(require_host)],
) -> dict:
    """End a session (host only)."""
    session_code = session_code.upper()
    
    session = await storage.update_session_status(session_code, "finished")
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Session not found"},
        )
    
    return {"ok": True}


# ============================================================================
# Player Endpoints
# ============================================================================


@router.post(
    "/{session_code}/players",
    response_model=JoinSessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def join_session(
    session_code: str,
    request: JoinSessionRequest,
    storage: Annotated[Storage, Depends(get_storage)],
) -> JoinSessionResponse:
    """Join an existing session as a player."""
    session_code = session_code.upper()
    
    session = await storage.get_session(session_code)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Session '{session_code}' not found"},
        )
    
    if session.status == "finished":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION", "message": "This session has ended"},
        )
    
    if session.status == "expired":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION", "message": "This session has expired"},
        )
    
    # Generate player ID and token
    player_id = generate_id("player_")
    player_token = create_player_token(player_id, session_code)
    
    # Add player to session
    await storage.add_player(
        session_code=session_code,
        player_id=player_id,
        display_name=request.display_name,
        is_host=False,
    )
    
    # Broadcast updated player list to all clients
    await broadcast_session_state(session_code)
    
    return JoinSessionResponse(player_id=player_id, player_token=player_token)


# ============================================================================
# Round Endpoints
# ============================================================================


@router.post(
    "/{session_code}/rounds",
    response_model=StartRoundResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def start_round(
    session_code: str,
    storage: Annotated[Storage, Depends(get_storage)],
    _: Annotated[str, Depends(require_host)],
    request: StartRoundRequest = None,
) -> StartRoundResponse:
    """Start a new round (host only)."""
    session_code = session_code.upper()
    
    session = await storage.get_session(session_code)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Session not found"},
        )
    
    # Check if game is over
    if session.current_round >= session.settings.rounds_total:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION", "message": "All rounds completed"},
        )
    
    # Increment round counter
    round_number = await storage.increment_session_round(session_code)
    
    # Fetch cat image
    image_url = await fetch_random_cat_url()
    
    now = datetime.now(timezone.utc)
    
    # Create round (no timer - rounds end when host reveals)
    round_id = generate_id("round_")
    round_obj = await storage.create_round(
        session_code=session_code,
        round_id=round_id,
        round_number=round_number,
        image_url=image_url,
        starts_at=now,
        ends_at=None,  # No timer for now (per BUILD_PROMPT non-goals)
    )
    
    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "SERVER_ERROR", "message": "Failed to create round"},
        )
    
    # Update session status
    await storage.update_session_status(session_code, "in_round")
    
    # Broadcast round started to all clients
    await broadcast_round_started(session_code, round_obj.model_dump(mode="json", by_alias=True))
    
    return StartRoundResponse(round=round_obj)


@router.post(
    "/{session_code}/rounds/{round_id}/reveal",
    response_model=RevealRoundResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def reveal_round(
    session_code: str,
    round_id: str,
    storage: Annotated[Storage, Depends(get_storage)],
    _: Annotated[str, Depends(require_host)],
) -> RevealRoundResponse:
    """Reveal round results and score captions (host only)."""
    session_code = session_code.upper()
    
    round_obj = await storage.get_round(session_code, round_id)
    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Round not found"},
        )
    
    # Get captions for this round
    captions = await storage.get_round_captions(session_code, round_id)
    
    # Score captions with LLM
    if captions:
        # Include player_id for reliable matching (display_name may not be unique)
        scores = await score_captions(
            image_url=round_obj.image_url,
            captions=[
                {"player_id": c.player_id, "player_name": c.display_name, "caption": c.text}
                for c in captions
            ],
        )
        
        # Build scores dict - match by player_id for reliability
        scores_dict: dict[str, Score] = {}
        for caption in captions:
            score_data = next(
                (s for s in scores if s.get("player_id") == caption.player_id),
                None,
            )
            if score_data:
                scores_dict[caption.player_id] = Score(
                    humour=score_data.get("humour", 5),
                    relevance=score_data.get("relevance", 5),
                    total=score_data.get("total", 10),
                    roast=score_data.get("roast_comment", ""),
                )
        
        await storage.update_caption_scores(session_code, round_id, scores_dict)
    
    # Update round status
    await storage.update_round_status(session_code, round_id, "revealed")
    
    # Check if game is over
    session = await storage.get_session(session_code)
    if session and session.current_round >= session.settings.rounds_total:
        await storage.update_session_status(session_code, "finished")
    else:
        await storage.update_session_status(session_code, "revealing")
    
    # Refetch captions with scores
    captions = await storage.get_round_captions(session_code, round_id)
    leaderboard = await storage.get_leaderboard(session_code)
    round_obj = await storage.get_round(session_code, round_id)
    
    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "SERVER_ERROR", "message": "Failed to retrieve round after update"},
        )
    
    # Broadcast results to all clients
    await broadcast_round_revealed(
        session_code,
        round_obj.model_dump(mode="json", by_alias=True),
        [c.model_dump(mode="json", by_alias=True) for c in captions],
        [e.model_dump(mode="json", by_alias=True) for e in leaderboard],
    )
    
    return RevealRoundResponse(
        round=round_obj,
        captions=captions,
        leaderboard=leaderboard,
    )


# ============================================================================
# Caption Endpoints
# ============================================================================


@router.post(
    "/{session_code}/rounds/{round_id}/captions",
    response_model=SubmitCaptionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def submit_caption(
    session_code: str,
    round_id: str,
    request: SubmitCaptionRequest,
    storage: Annotated[Storage, Depends(get_storage)],
    player_id: Annotated[str, Depends(get_current_player_id)],
) -> SubmitCaptionResponse:
    """Submit a caption for the current round."""
    session_code = session_code.upper()
    
    # Validate session exists and is in round
    session = await storage.get_session(session_code)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Session not found"},
        )
    
    if session.status != "in_round":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION", "message": "No active round"},
        )
    
    # Validate round exists
    round_obj = await storage.get_round(session_code, round_id)
    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Round not found"},
        )
    
    # Check word limit (15 words max)
    words = request.text.strip().split()
    if len(words) > 15:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION", "message": "Caption exceeds 15 word limit"},
        )
    
    # Check if already submitted
    if await storage.has_submitted(session_code, round_id, player_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION", "message": "Already submitted for this round"},
        )
    
    # Submit caption
    caption_id = generate_id("caption_")
    caption = await storage.submit_caption(
        session_code=session_code,
        round_id=round_id,
        caption_id=caption_id,
        player_id=player_id,
        text=request.text.strip(),
    )
    
    if not caption:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION", "message": "Failed to submit caption"},
        )
    
    # Broadcast that this player has submitted
    await broadcast_caption_locked(session_code, round_id, player_id)
    
    return SubmitCaptionResponse(caption_id=caption_id, locked=True)

