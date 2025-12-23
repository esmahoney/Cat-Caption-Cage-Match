"""
Pydantic models for API request/response schemas.

These define the shape of data flowing through the REST API and Socket.IO events.
All models use camelCase for JSON serialization to match the API contract.
"""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelCaseModel(BaseModel):
    """
    Base model that converts snake_case to camelCase for JSON serialization.
    
    This ensures API responses match the contract (e.g., session_id → sessionId).
    Also accepts camelCase in request bodies for client convenience.
    """
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,  # Accept both snake_case and camelCase in requests
        serialize_by_alias=True,  # Always serialize using camelCase aliases
    )


# ============================================================================
# Core Domain Models
# ============================================================================

class SessionSettings(CamelCaseModel):
    """Configurable session settings."""
    rounds_total: int = Field(default=3, ge=1, le=10)
    # Note: round_seconds removed - timers are a non-goal for v2


class Session(CamelCaseModel):
    """Session state."""
    session_id: str
    session_code: str
    status: Literal["lobby", "in_round", "revealing", "finished", "expired"]
    host_player_id: str
    settings: SessionSettings
    current_round: int = 0
    created_at: datetime
    expires_at: datetime


class Player(CamelCaseModel):
    """Player in a session."""
    player_id: str
    display_name: str
    is_host: bool = False
    joined_at: datetime


class Round(CamelCaseModel):
    """A single round."""
    round_id: str
    number: int
    image_url: str
    status: Literal["active", "scoring", "revealed"]
    starts_at: datetime
    ends_at: Optional[datetime] = None


class Score(CamelCaseModel):
    """Caption score from LLM."""
    humour: int = Field(ge=0, le=10)
    relevance: int = Field(ge=0, le=10)
    total: int = Field(ge=0, le=20)
    roast: str = ""


class Caption(CamelCaseModel):
    """A submitted caption with score."""
    caption_id: str
    player_id: str
    display_name: str
    text: str
    submitted_at: datetime
    score: Optional[Score] = None


class LeaderboardEntry(CamelCaseModel):
    """Leaderboard entry."""
    player_id: str
    display_name: str
    total_score: int
    rank: int


# ============================================================================
# API Request Models
# ============================================================================

class CreateSessionRequest(CamelCaseModel):
    """Request to create a new session."""
    host_display_name: str = Field(min_length=1, max_length=30)
    settings: SessionSettings = Field(default_factory=SessionSettings)


class JoinSessionRequest(CamelCaseModel):
    """Request to join a session."""
    display_name: str = Field(min_length=1, max_length=30)


class SubmitCaptionRequest(CamelCaseModel):
    """Request to submit a caption."""
    text: str = Field(min_length=1, max_length=200)


class StartRoundRequest(CamelCaseModel):
    """Request to start a round (optional overrides)."""
    # No configurable options for now - timers are a non-goal
    pass


# ============================================================================
# API Response Models
# ============================================================================

class PlayerCredentials(CamelCaseModel):
    """Player ID and token returned on join/create."""
    player_id: str
    player_token: str


class CreateSessionResponse(CamelCaseModel):
    """Response when creating a session."""
    session: Session
    host: PlayerCredentials


class JoinSessionResponse(CamelCaseModel):
    """Response when joining a session."""
    player_id: str
    player_token: str


class SessionStateResponse(CamelCaseModel):
    """Full session state for initial load or reconnect."""
    session: Session
    players: list[Player]
    current_round: Optional[Round] = None
    leaderboard: list[LeaderboardEntry]


class StartRoundResponse(CamelCaseModel):
    """Response when starting a round."""
    round: Round


class SubmitCaptionResponse(CamelCaseModel):
    """Response when submitting a caption."""
    caption_id: str
    locked: bool = True


class RevealRoundResponse(CamelCaseModel):
    """Response when revealing round results."""
    round: Round
    captions: list[Caption]
    leaderboard: list[LeaderboardEntry]


class HealthResponse(CamelCaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "2.0.0"


class ErrorResponse(CamelCaseModel):
    """Standard error response."""
    code: Literal["NOT_FOUND", "UNAUTHORIZED", "VALIDATION", "RATE_LIMIT", "SERVER_ERROR"]
    message: str

