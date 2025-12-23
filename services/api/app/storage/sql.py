"""
SQL-based storage implementation using SQLAlchemy.

Works with both SQLite (dev) and PostgreSQL (production).
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Session, SessionSettings, Player, Round, Caption, Score, LeaderboardEntry
)
from ..db.models import SessionModel, PlayerModel, RoundModel, CaptionModel
from ..db.connection import get_db_session_context
from .base import Storage


class SQLStorage(Storage):
    """
    SQL-based storage using SQLAlchemy async sessions.
    
    This implementation works with any SQLAlchemy-supported database.
    """
    
    def __init__(self, session_expiry_hours: int = 2):
        self.session_expiry_hours = session_expiry_hours
    
    # ========================================================================
    # Helper methods
    # ========================================================================
    
    def _session_model_to_pydantic(self, model: SessionModel) -> Session:
        """Convert SQLAlchemy SessionModel to Pydantic Session."""
        return Session(
            session_id=model.id,
            session_code=model.code,
            status=model.status,
            host_player_id=model.host_player_id,
            settings=SessionSettings(**model.settings),
            current_round=model.current_round,
            created_at=model.created_at.replace(tzinfo=timezone.utc) if model.created_at.tzinfo is None else model.created_at,
            expires_at=model.expires_at.replace(tzinfo=timezone.utc) if model.expires_at.tzinfo is None else model.expires_at,
        )
    
    def _player_model_to_pydantic(self, model: PlayerModel) -> Player:
        """Convert SQLAlchemy PlayerModel to Pydantic Player."""
        return Player(
            player_id=model.id,
            display_name=model.display_name,
            is_host=model.is_host,
            joined_at=model.joined_at.replace(tzinfo=timezone.utc) if model.joined_at.tzinfo is None else model.joined_at,
        )
    
    def _round_model_to_pydantic(self, model: RoundModel) -> Round:
        """Convert SQLAlchemy RoundModel to Pydantic Round."""
        ends_at = model.ends_at
        if ends_at and ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=timezone.utc)
        return Round(
            round_id=model.id,
            number=model.number,
            image_url=model.image_url,
            status=model.status,
            starts_at=model.starts_at.replace(tzinfo=timezone.utc) if model.starts_at.tzinfo is None else model.starts_at,
            ends_at=ends_at,
        )
    
    def _caption_model_to_pydantic(self, model: CaptionModel, display_name: str) -> Caption:
        """Convert SQLAlchemy CaptionModel to Pydantic Caption."""
        score = None
        if model.score_total is not None:
            score = Score(
                humour=model.score_humour or 0,
                relevance=model.score_relevance or 0,
                total=model.score_total,
                roast=model.roast or "",
            )
        return Caption(
            caption_id=model.id,
            player_id=model.player_id,
            display_name=display_name,
            text=model.text,
            submitted_at=model.submitted_at.replace(tzinfo=timezone.utc) if model.submitted_at.tzinfo is None else model.submitted_at,
            score=score,
        )
    
    async def _get_session_id_from_code(self, db: AsyncSession, session_code: str) -> Optional[str]:
        """Get session ID from session code."""
        result = await db.execute(
            select(SessionModel.id).where(SessionModel.code == session_code)
        )
        row = result.scalar_one_or_none()
        return row
    
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
        
        async with get_db_session_context() as db:
            # Create session
            session_model = SessionModel(
                id=session_id,
                code=session_code,
                status="lobby",
                host_player_id=host_player_id,
                settings=settings.model_dump(),
                current_round=0,
                created_at=now,
                expires_at=now + timedelta(hours=self.session_expiry_hours),
            )
            db.add(session_model)
            
            # Create host player
            player_model = PlayerModel(
                id=host_player_id,
                session_id=session_id,
                display_name=host_display_name,
                is_host=True,
                joined_at=now,
            )
            db.add(player_model)
            
            await db.flush()
            return self._session_model_to_pydantic(session_model)
    
    async def get_session(self, session_code: str) -> Optional[Session]:
        async with get_db_session_context() as db:
            result = await db.execute(
                select(SessionModel).where(SessionModel.code == session_code)
            )
            model = result.scalar_one_or_none()
            if model:
                return self._session_model_to_pydantic(model)
            return None
    
    async def get_session_by_id(self, session_id: str) -> Optional[Session]:
        async with get_db_session_context() as db:
            result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            model = result.scalar_one_or_none()
            if model:
                return self._session_model_to_pydantic(model)
            return None
    
    async def update_session_status(
        self, session_code: str, status: str
    ) -> Optional[Session]:
        async with get_db_session_context() as db:
            result = await db.execute(
                select(SessionModel).where(SessionModel.code == session_code)
            )
            model = result.scalar_one_or_none()
            if model:
                model.status = status
                await db.flush()
                return self._session_model_to_pydantic(model)
            return None
    
    async def session_exists(self, session_code: str) -> bool:
        async with get_db_session_context() as db:
            result = await db.execute(
                select(SessionModel.id).where(SessionModel.code == session_code)
            )
            return result.scalar_one_or_none() is not None
    
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
        async with get_db_session_context() as db:
            session_id = await self._get_session_id_from_code(db, session_code)
            if not session_id:
                return None
            
            player_model = PlayerModel(
                id=player_id,
                session_id=session_id,
                display_name=display_name,
                is_host=is_host,
                joined_at=datetime.now(timezone.utc),
            )
            db.add(player_model)
            await db.flush()
            return self._player_model_to_pydantic(player_model)
    
    async def get_player(self, session_code: str, player_id: str) -> Optional[Player]:
        async with get_db_session_context() as db:
            session_id = await self._get_session_id_from_code(db, session_code)
            if not session_id:
                return None
            
            result = await db.execute(
                select(PlayerModel).where(
                    PlayerModel.id == player_id,
                    PlayerModel.session_id == session_id,
                )
            )
            model = result.scalar_one_or_none()
            if model:
                return self._player_model_to_pydantic(model)
            return None
    
    async def get_players(self, session_code: str) -> list[Player]:
        async with get_db_session_context() as db:
            session_id = await self._get_session_id_from_code(db, session_code)
            if not session_id:
                return []
            
            result = await db.execute(
                select(PlayerModel)
                .where(PlayerModel.session_id == session_id)
                .order_by(PlayerModel.is_host.desc(), PlayerModel.joined_at)
            )
            models = result.scalars().all()
            return [self._player_model_to_pydantic(m) for m in models]
    
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
        async with get_db_session_context() as db:
            session_id = await self._get_session_id_from_code(db, session_code)
            if not session_id:
                return None
            
            round_model = RoundModel(
                id=round_id,
                session_id=session_id,
                number=round_number,
                image_url=image_url,
                status="active",
                starts_at=starts_at,
                ends_at=ends_at,
            )
            db.add(round_model)
            await db.flush()
            return self._round_model_to_pydantic(round_model)
    
    async def get_current_round(self, session_code: str) -> Optional[Round]:
        async with get_db_session_context() as db:
            session_id = await self._get_session_id_from_code(db, session_code)
            if not session_id:
                return None
            
            result = await db.execute(
                select(RoundModel)
                .where(
                    RoundModel.session_id == session_id,
                    RoundModel.status == "active",
                )
                .order_by(RoundModel.number.desc())
                .limit(1)
            )
            model = result.scalar_one_or_none()
            if model:
                return self._round_model_to_pydantic(model)
            return None
    
    async def get_round(self, session_code: str, round_id: str) -> Optional[Round]:
        async with get_db_session_context() as db:
            result = await db.execute(
                select(RoundModel).where(RoundModel.id == round_id)
            )
            model = result.scalar_one_or_none()
            if model:
                return self._round_model_to_pydantic(model)
            return None
    
    async def update_round_status(
        self, session_code: str, round_id: str, status: str
    ) -> Optional[Round]:
        async with get_db_session_context() as db:
            result = await db.execute(
                select(RoundModel).where(RoundModel.id == round_id)
            )
            model = result.scalar_one_or_none()
            if model:
                model.status = status
                await db.flush()
                return self._round_model_to_pydantic(model)
            return None
    
    async def increment_session_round(self, session_code: str) -> int:
        async with get_db_session_context() as db:
            result = await db.execute(
                select(SessionModel).where(SessionModel.code == session_code)
            )
            model = result.scalar_one_or_none()
            if model:
                model.current_round += 1
                await db.flush()
                return model.current_round
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
        
        async with get_db_session_context() as db:
            # Get player display name
            player_result = await db.execute(
                select(PlayerModel.display_name).where(PlayerModel.id == player_id)
            )
            display_name = player_result.scalar_one_or_none()
            if not display_name:
                return None
            
            caption_model = CaptionModel(
                id=caption_id,
                round_id=round_id,
                player_id=player_id,
                text=text,
                submitted_at=datetime.now(timezone.utc),
            )
            db.add(caption_model)
            await db.flush()
            return self._caption_model_to_pydantic(caption_model, display_name)
    
    async def has_submitted(
        self, session_code: str, round_id: str, player_id: str
    ) -> bool:
        async with get_db_session_context() as db:
            result = await db.execute(
                select(CaptionModel.id).where(
                    CaptionModel.round_id == round_id,
                    CaptionModel.player_id == player_id,
                )
            )
            return result.scalar_one_or_none() is not None
    
    async def get_round_captions(
        self, session_code: str, round_id: str
    ) -> list[Caption]:
        async with get_db_session_context() as db:
            result = await db.execute(
                select(CaptionModel, PlayerModel.display_name)
                .join(PlayerModel, CaptionModel.player_id == PlayerModel.id)
                .where(CaptionModel.round_id == round_id)
                .order_by(CaptionModel.score_total.desc().nullslast())
            )
            rows = result.all()
            return [
                self._caption_model_to_pydantic(caption, display_name)
                for caption, display_name in rows
            ]
    
    async def get_submission_count(self, session_code: str, round_id: str) -> int:
        async with get_db_session_context() as db:
            result = await db.execute(
                select(func.count(CaptionModel.id)).where(
                    CaptionModel.round_id == round_id
                )
            )
            return result.scalar_one()
    
    async def update_caption_scores(
        self,
        session_code: str,
        round_id: str,
        scores: dict[str, Score],
    ) -> None:
        async with get_db_session_context() as db:
            result = await db.execute(
                select(CaptionModel).where(CaptionModel.round_id == round_id)
            )
            captions = result.scalars().all()
            
            for caption in captions:
                if caption.player_id in scores:
                    score = scores[caption.player_id]
                    caption.score_humour = score.humour
                    caption.score_relevance = score.relevance
                    caption.score_total = score.total
                    caption.roast = score.roast
            
            await db.flush()
    
    # ========================================================================
    # Leaderboard
    # ========================================================================
    
    async def get_leaderboard(self, session_code: str) -> list[LeaderboardEntry]:
        async with get_db_session_context() as db:
            session_id = await self._get_session_id_from_code(db, session_code)
            if not session_id:
                return []
            
            # Get all players with their total scores
            result = await db.execute(
                select(
                    PlayerModel.id,
                    PlayerModel.display_name,
                    func.coalesce(func.sum(CaptionModel.score_total), 0).label("total_score"),
                )
                .outerjoin(CaptionModel, PlayerModel.id == CaptionModel.player_id)
                .where(PlayerModel.session_id == session_id)
                .group_by(PlayerModel.id, PlayerModel.display_name)
                .order_by(func.coalesce(func.sum(CaptionModel.score_total), 0).desc())
            )
            rows = result.all()
            
            return [
                LeaderboardEntry(
                    player_id=row.id,
                    display_name=row.display_name,
                    total_score=int(row.total_score),
                    rank=i + 1,
                )
                for i, row in enumerate(rows)
            ]
    
    # ========================================================================
    # Cleanup
    # ========================================================================
    
    async def cleanup_expired_sessions(self) -> int:
        now = datetime.now(timezone.utc)
        async with get_db_session_context() as db:
            # Count before delete
            count_result = await db.execute(
                select(func.count(SessionModel.id)).where(
                    SessionModel.expires_at < now
                )
            )
            count = count_result.scalar_one()
            
            # Delete expired sessions (cascades to players, rounds, captions)
            await db.execute(
                delete(SessionModel).where(SessionModel.expires_at < now)
            )
            
            return count

