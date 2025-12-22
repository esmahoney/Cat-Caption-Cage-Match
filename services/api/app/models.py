"""
Pydantic models for API request/response schemas.

These define the shape of data flowing through the REST API and Socket.IO events.
"""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


# ============================================================================
# Core Domain Models
# ============================================================================

class SessionSettings(BaseModel):
    """Configurable session settings."""
    rounds_total: int = Field(default=3, ge=1, le=10)
    # Note: round_seconds removed - timers are a non-goal for v2


class Session(BaseModel):
    """Session state."""
    session_id: str
    session_code: str
    status: Literal["lobby", "in_round", "revealing", "finished", "expired"]
    host_player_id: str
    settings: SessionSettings
    current_round: int = 0
    created_at: datetime
    expires_at: datetime


class Player(BaseModel):
    """Player in a session."""
    player_id: str
    display_name: str
    is_host: bool = False
    joined_at: datetime


class Round(BaseModel):
    """A single round."""
    round_id: str
    number: int
    image_url: str
    status: Literal["active", "scoring", "revealed"]
    starts_at: datetime
    ends_at: Optional[datetime] = None


class Score(BaseModel):
    """Caption score from LLM."""
    humour: int = Field(ge=0, le=10)
    relevance: int = Field(ge=0, le=10)
    total: int = Field(ge=0, le=20)
    roast: str = ""


class Caption(BaseModel):
    """A submitted caption with score."""
    caption_id: str
    player_id: str
    display_name: str
    text: str
    submitted_at: datetime
    score: Optional[Score] = None


class LeaderboardEntry(BaseModel):
    """Leaderboard entry."""
    player_id: str
    display_name: str
    total_score: int
    rank: int


# ============================================================================
# API Request Models
# ============================================================================

class CreateSessionRequest(BaseModel):
    """Request to create a new session."""
    host_display_name: str = Field(min_length=1, max_length=30)
    settings: SessionSettings = Field(default_factory=SessionSettings)


class JoinSessionRequest(BaseModel):
    """Request to join a session."""
    display_name: str = Field(min_length=1, max_length=30)


class SubmitCaptionRequest(BaseModel):
    """Request to submit a caption."""
    text: str = Field(min_length=1, max_length=200)


class StartRoundRequest(BaseModel):
    """Request to start a round (optional overrides)."""
    # No configurable options for now - timers are a non-goal
    pass


# ============================================================================
# API Response Models
# ============================================================================

class PlayerCredentials(BaseModel):
    """Player ID and token returned on join/create."""
    player_id: str
    player_token: str


class CreateSessionResponse(BaseModel):
    """Response when creating a session."""
    session: Session
    host: PlayerCredentials


class JoinSessionResponse(BaseModel):
    """Response when joining a session."""
    player_id: str
    player_token: str


class SessionStateResponse(BaseModel):
    """Full session state for initial load or reconnect."""
    session: Session
    players: list[Player]
    current_round: Optional[Round] = None
    leaderboard: list[LeaderboardEntry]


class StartRoundResponse(BaseModel):
    """Response when starting a round."""
    round: Round


class SubmitCaptionResponse(BaseModel):
    """Response when submitting a caption."""
    caption_id: str
    locked: bool = True


class RevealRoundResponse(BaseModel):
    """Response when revealing round results."""
    round: Round
    captions: list[Caption]
    leaderboard: list[LeaderboardEntry]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "2.0.0"


class ErrorResponse(BaseModel):
    """Standard error response."""
    code: Literal["NOT_FOUND", "UNAUTHORIZED", "VALIDATION", "RATE_LIMIT", "SERVER_ERROR"]
    message: str

