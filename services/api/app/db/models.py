"""
SQLAlchemy ORM models for Cat Caption Cage Match.

These map to the database tables and mirror the Pydantic models in models.py.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class SessionModel(Base):
    """Game session table."""
    __tablename__ = "sessions"
    
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="lobby")
    host_player_id: Mapped[str] = mapped_column(String(100))
    
    # Settings stored as JSON
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    
    current_round: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    
    # Relationships
    players: Mapped[list["PlayerModel"]] = relationship(
        "PlayerModel", back_populates="session", cascade="all, delete-orphan"
    )
    rounds: Mapped[list["RoundModel"]] = relationship(
        "RoundModel", back_populates="session", cascade="all, delete-orphan"
    )


class PlayerModel(Base):
    """Player in a session."""
    __tablename__ = "players"
    
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(50))
    is_host: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session: Mapped["SessionModel"] = relationship("SessionModel", back_populates="players")
    captions: Mapped[list["CaptionModel"]] = relationship(
        "CaptionModel", back_populates="player", cascade="all, delete-orphan"
    )


class RoundModel(Base):
    """A single round in a session."""
    __tablename__ = "rounds"
    
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(Integer)
    image_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    session: Mapped["SessionModel"] = relationship("SessionModel", back_populates="rounds")
    captions: Mapped[list["CaptionModel"]] = relationship(
        "CaptionModel", back_populates="round", cascade="all, delete-orphan"
    )


class CaptionModel(Base):
    """A player's caption submission for a round."""
    __tablename__ = "captions"
    
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    round_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("rounds.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Score fields (nullable until scored)
    score_humour: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_relevance: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    roast: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    round: Mapped["RoundModel"] = relationship("RoundModel", back_populates="captions")
    player: Mapped["PlayerModel"] = relationship("PlayerModel", back_populates="captions")

