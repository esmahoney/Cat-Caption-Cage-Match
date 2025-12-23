"""Initial schema for Cat Caption Cage Match

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sessions table
    op.create_table(
        'sessions',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('code', sa.String(10), unique=True, nullable=False, index=True),
        sa.Column('status', sa.String(20), nullable=False, default='lobby'),
        sa.Column('host_player_id', sa.String(100), nullable=False),
        sa.Column('settings', sa.JSON, nullable=False, default=dict),
        sa.Column('current_round', sa.Integer, nullable=False, default=0),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('expires_at', sa.DateTime, nullable=False),
    )
    
    # Create players table
    op.create_table(
        'players',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('session_id', sa.String(100), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('display_name', sa.String(50), nullable=False),
        sa.Column('is_host', sa.Boolean, nullable=False, default=False),
        sa.Column('joined_at', sa.DateTime, nullable=False),
    )
    
    # Create rounds table
    op.create_table(
        'rounds',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('session_id', sa.String(100), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('number', sa.Integer, nullable=False),
        sa.Column('image_url', sa.Text, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='active'),
        sa.Column('starts_at', sa.DateTime, nullable=False),
        sa.Column('ends_at', sa.DateTime, nullable=True),
    )
    
    # Create captions table
    op.create_table(
        'captions',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('round_id', sa.String(100), sa.ForeignKey('rounds.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('player_id', sa.String(100), sa.ForeignKey('players.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('submitted_at', sa.DateTime, nullable=False),
        sa.Column('score_humour', sa.Integer, nullable=True),
        sa.Column('score_relevance', sa.Integer, nullable=True),
        sa.Column('score_total', sa.Integer, nullable=True),
        sa.Column('roast', sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table('captions')
    op.drop_table('rounds')
    op.drop_table('players')
    op.drop_table('sessions')

