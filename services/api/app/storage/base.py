"""
Abstract base class for storage implementations.

All storage backends must implement this interface.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from ..models import (
    Session, SessionSettings, Player, Round, Caption, Score, LeaderboardEntry
)


class Storage(ABC):
    """Abstract storage interface for game data."""
    
    # ========================================================================
    # Session Management
    # ========================================================================
    
    @abstractmethod
    async def create_session(
        self,
        session_code: str,
        host_player_id: str,
        host_display_name: str,
        settings: SessionSettings,
    ) -> Session:
        """Create a new session with the host as the first player."""
        pass
    
    @abstractmethod
    async def get_session(self, session_code: str) -> Optional[Session]:
        """Get session by code. Returns None if not found."""
        pass
    
    @abstractmethod
    async def get_session_by_id(self, session_id: str) -> Optional[Session]:
        """Get session by ID. Returns None if not found."""
        pass
    
    @abstractmethod
    async def update_session_status(
        self, session_code: str, status: str
    ) -> Optional[Session]:
        """Update session status. Returns updated session or None."""
        pass
    
    @abstractmethod
    async def session_exists(self, session_code: str) -> bool:
        """Check if a session with this code exists."""
        pass
    
    # ========================================================================
    # Player Management
    # ========================================================================
    
    @abstractmethod
    async def add_player(
        self,
        session_code: str,
        player_id: str,
        display_name: str,
        is_host: bool = False,
    ) -> Optional[Player]:
        """Add a player to a session. Returns the player or None if session not found."""
        pass
    
    @abstractmethod
    async def get_player(self, session_code: str, player_id: str) -> Optional[Player]:
        """Get a specific player from a session."""
        pass
    
    @abstractmethod
    async def get_players(self, session_code: str) -> list[Player]:
        """Get all players in a session."""
        pass
    
    @abstractmethod
    async def is_host(self, session_code: str, player_id: str) -> bool:
        """Check if a player is the host of a session."""
        pass
    
    # ========================================================================
    # Round Management
    # ========================================================================
    
    @abstractmethod
    async def create_round(
        self,
        session_code: str,
        round_id: str,
        round_number: int,
        image_url: str,
        starts_at: datetime,
        ends_at: Optional[datetime] = None,
    ) -> Optional[Round]:
        """Create a new round. Returns the round or None if session not found."""
        pass
    
    @abstractmethod
    async def get_current_round(self, session_code: str) -> Optional[Round]:
        """Get the current active round for a session."""
        pass
    
    @abstractmethod
    async def get_round(self, session_code: str, round_id: str) -> Optional[Round]:
        """Get a specific round by ID."""
        pass
    
    @abstractmethod
    async def update_round_status(
        self, session_code: str, round_id: str, status: str
    ) -> Optional[Round]:
        """Update round status. Returns updated round or None."""
        pass
    
    @abstractmethod
    async def increment_session_round(self, session_code: str) -> int:
        """Increment the session's current round counter. Returns new round number."""
        pass
    
    # ========================================================================
    # Caption Management
    # ========================================================================
    
    @abstractmethod
    async def submit_caption(
        self,
        session_code: str,
        round_id: str,
        caption_id: str,
        player_id: str,
        text: str,
    ) -> Optional[Caption]:
        """Submit a caption. Returns the caption or None if already submitted."""
        pass
    
    @abstractmethod
    async def has_submitted(
        self, session_code: str, round_id: str, player_id: str
    ) -> bool:
        """Check if a player has already submitted for this round."""
        pass
    
    @abstractmethod
    async def get_round_captions(
        self, session_code: str, round_id: str
    ) -> list[Caption]:
        """Get all captions for a round."""
        pass
    
    @abstractmethod
    async def get_submission_count(self, session_code: str, round_id: str) -> int:
        """Get the number of submissions for a round."""
        pass
    
    @abstractmethod
    async def update_caption_scores(
        self,
        session_code: str,
        round_id: str,
        scores: dict[str, Score],  # player_id -> Score
    ) -> None:
        """Update scores for all captions in a round."""
        pass
    
    # ========================================================================
    # Leaderboard
    # ========================================================================
    
    @abstractmethod
    async def get_leaderboard(self, session_code: str) -> list[LeaderboardEntry]:
        """Get the current leaderboard for a session."""
        pass
    
    # ========================================================================
    # Cleanup
    # ========================================================================
    
    @abstractmethod
    async def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions. Returns count of removed sessions."""
        pass

