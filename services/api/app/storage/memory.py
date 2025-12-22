"""
In-memory storage implementation for development and testing.

Data is lost when the server restarts - by design for dev/test scenarios.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from collections import defaultdict

from ..models import (
    Session, SessionSettings, Player, Round, Caption, Score, LeaderboardEntry
)
from .base import Storage


class InMemoryStorage(Storage):
    """In-memory storage using Python dictionaries."""
    
    def __init__(self, session_expiry_hours: int = 2):
        self.session_expiry_hours = session_expiry_hours
        
        # Primary storage
        self._sessions: dict[str, Session] = {}  # session_code -> Session
        self._players: dict[str, dict[str, Player]] = defaultdict(dict)  # session_code -> {player_id -> Player}
        self._rounds: dict[str, dict[str, Round]] = defaultdict(dict)  # session_code -> {round_id -> Round}
        self._captions: dict[str, dict[str, list[Caption]]] = defaultdict(lambda: defaultdict(list))  # session_code -> {round_id -> [Caption]}
        
        # Index for faster lookups
        self._session_id_to_code: dict[str, str] = {}  # session_id -> session_code
    
    # ========================================================================
    # Session Management
    # ========================================================================
    
    async def create_session(
        self,
        session_code: str,
        host_player_id: str,
        host_display_name: str,
        settings: SessionSettings,
    ) -> Session:
        now = datetime.now(timezone.utc)
        session_id = f"sess_{session_code}_{int(now.timestamp())}"
        
        session = Session(
            session_id=session_id,
            session_code=session_code,
            status="lobby",
            host_player_id=host_player_id,
            settings=settings,
            current_round=0,
            created_at=now,
            expires_at=now + timedelta(hours=self.session_expiry_hours),
        )
        
        self._sessions[session_code] = session
        self._session_id_to_code[session_id] = session_code
        
        # Add host as first player
        await self.add_player(session_code, host_player_id, host_display_name, is_host=True)
        
        return session
    
    async def get_session(self, session_code: str) -> Optional[Session]:
        return self._sessions.get(session_code)
    
    async def get_session_by_id(self, session_id: str) -> Optional[Session]:
        session_code = self._session_id_to_code.get(session_id)
        if session_code:
            return self._sessions.get(session_code)
        return None
    
    async def update_session_status(
        self, session_code: str, status: str
    ) -> Optional[Session]:
        session = self._sessions.get(session_code)
        if session:
            # Create updated session (Pydantic models are immutable by default)
            updated = session.model_copy(update={"status": status})
            self._sessions[session_code] = updated
            return updated
        return None
    
    async def session_exists(self, session_code: str) -> bool:
        return session_code in self._sessions
    
    # ========================================================================
    # Player Management
    # ========================================================================
    
    async def add_player(
        self,
        session_code: str,
        player_id: str,
        display_name: str,
        is_host: bool = False,
    ) -> Optional[Player]:
        if session_code not in self._sessions:
            return None
        
        player = Player(
            player_id=player_id,
            display_name=display_name,
            is_host=is_host,
            joined_at=datetime.now(timezone.utc),
        )
        
        self._players[session_code][player_id] = player
        return player
    
    async def get_player(self, session_code: str, player_id: str) -> Optional[Player]:
        return self._players.get(session_code, {}).get(player_id)
    
    async def get_players(self, session_code: str) -> list[Player]:
        players = list(self._players.get(session_code, {}).values())
        # Sort: host first, then by join time
        return sorted(players, key=lambda p: (not p.is_host, p.joined_at))
    
    async def is_host(self, session_code: str, player_id: str) -> bool:
        player = await self.get_player(session_code, player_id)
        return player.is_host if player else False
    
    # ========================================================================
    # Round Management
    # ========================================================================
    
    async def create_round(
        self,
        session_code: str,
        round_id: str,
        round_number: int,
        image_url: str,
        starts_at: datetime,
        ends_at: Optional[datetime] = None,
    ) -> Optional[Round]:
        if session_code not in self._sessions:
            return None
        
        round_obj = Round(
            round_id=round_id,
            number=round_number,
            image_url=image_url,
            status="active",
            starts_at=starts_at,
            ends_at=ends_at,
        )
        
        self._rounds[session_code][round_id] = round_obj
        return round_obj
    
    async def get_current_round(self, session_code: str) -> Optional[Round]:
        rounds = self._rounds.get(session_code, {})
        # Find the most recent active round
        active_rounds = [r for r in rounds.values() if r.status == "active"]
        if active_rounds:
            return max(active_rounds, key=lambda r: r.number)
        return None
    
    async def get_round(self, session_code: str, round_id: str) -> Optional[Round]:
        return self._rounds.get(session_code, {}).get(round_id)
    
    async def update_round_status(
        self, session_code: str, round_id: str, status: str
    ) -> Optional[Round]:
        round_obj = self._rounds.get(session_code, {}).get(round_id)
        if round_obj:
            updated = round_obj.model_copy(update={"status": status})
            self._rounds[session_code][round_id] = updated
            return updated
        return None
    
    async def increment_session_round(self, session_code: str) -> int:
        session = self._sessions.get(session_code)
        if session:
            new_round = session.current_round + 1
            updated = session.model_copy(update={"current_round": new_round})
            self._sessions[session_code] = updated
            return new_round
        return 0
    
    # ========================================================================
    # Caption Management
    # ========================================================================
    
    async def submit_caption(
        self,
        session_code: str,
        round_id: str,
        caption_id: str,
        player_id: str,
        text: str,
    ) -> Optional[Caption]:
        # Check if already submitted
        if await self.has_submitted(session_code, round_id, player_id):
            return None
        
        # Get player display name
        player = await self.get_player(session_code, player_id)
        if not player:
            return None
        
        caption = Caption(
            caption_id=caption_id,
            player_id=player_id,
            display_name=player.display_name,
            text=text,
            submitted_at=datetime.now(timezone.utc),
            score=None,
        )
        
        self._captions[session_code][round_id].append(caption)
        return caption
    
    async def has_submitted(
        self, session_code: str, round_id: str, player_id: str
    ) -> bool:
        captions = self._captions.get(session_code, {}).get(round_id, [])
        return any(c.player_id == player_id for c in captions)
    
    async def get_round_captions(
        self, session_code: str, round_id: str
    ) -> list[Caption]:
        return self._captions.get(session_code, {}).get(round_id, [])
    
    async def get_submission_count(self, session_code: str, round_id: str) -> int:
        return len(self._captions.get(session_code, {}).get(round_id, []))
    
    async def update_caption_scores(
        self,
        session_code: str,
        round_id: str,
        scores: dict[str, Score],
    ) -> None:
        captions = self._captions.get(session_code, {}).get(round_id, [])
        for i, caption in enumerate(captions):
            if caption.player_id in scores:
                updated = caption.model_copy(update={"score": scores[caption.player_id]})
                self._captions[session_code][round_id][i] = updated
    
    # ========================================================================
    # Leaderboard
    # ========================================================================
    
    async def get_leaderboard(self, session_code: str) -> list[LeaderboardEntry]:
        players = await self.get_players(session_code)
        
        # Calculate total scores per player
        player_scores: dict[str, int] = {p.player_id: 0 for p in players}
        
        for round_captions in self._captions.get(session_code, {}).values():
            for caption in round_captions:
                if caption.score:
                    player_scores[caption.player_id] = (
                        player_scores.get(caption.player_id, 0) + caption.score.total
                    )
        
        # Build leaderboard entries
        entries = []
        for player in players:
            entries.append(LeaderboardEntry(
                player_id=player.player_id,
                display_name=player.display_name,
                total_score=player_scores.get(player.player_id, 0),
                rank=0,  # Will be set after sorting
            ))
        
        # Sort by score descending
        entries.sort(key=lambda e: e.total_score, reverse=True)
        
        # Assign ranks
        for i, entry in enumerate(entries):
            entries[i] = entry.model_copy(update={"rank": i + 1})
        
        return entries
    
    # ========================================================================
    # Cleanup
    # ========================================================================
    
    async def cleanup_expired_sessions(self) -> int:
        now = datetime.now(timezone.utc)
        expired_codes = [
            code for code, session in self._sessions.items()
            if session.expires_at < now
        ]
        
        for code in expired_codes:
            session = self._sessions.pop(code, None)
            if session:
                self._session_id_to_code.pop(session.session_id, None)
            self._players.pop(code, None)
            self._rounds.pop(code, None)
            self._captions.pop(code, None)
        
        return len(expired_codes)

