"""
storage.py - DuckDB database access for Cat Caption Cage Match

Handles all persistence: sessions, players, rounds, captions, and scores.
Uses in-memory DuckDB for simplicity (can easily switch to file-based).
"""

import duckdb
import random
import string
from datetime import datetime
from typing import Optional


# In-memory DuckDB connection (shared across the app)
_con: Optional[duckdb.DuckDBPyConnection] = None


def get_connection() -> duckdb.DuckDBPyConnection:
    """Get or create the database connection."""
    global _con
    if _con is None:
        _con = duckdb.connect()  # In-memory database
        _init_schema(_con)
    return _con


def _init_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Initialize the database schema."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id VARCHAR PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR DEFAULT 'lobby',  -- lobby, playing, game_over, finished
            current_round INT DEFAULT 0,
            current_game INT DEFAULT 1,
            total_rounds INT DEFAULT 5,
            round_timer_seconds INT DEFAULT 120
        )
    """)
    
    con.execute("""
        CREATE TABLE IF NOT EXISTS players (
            session_id VARCHAR,
            player_id VARCHAR,
            name VARCHAR,
            is_host BOOLEAN DEFAULT FALSE,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (session_id, player_id)
        )
    """)
    
    con.execute("""
        CREATE TABLE IF NOT EXISTS rounds (
            session_id VARCHAR,
            game_number INT,
            round_number INT,
            image_url VARCHAR,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            PRIMARY KEY (session_id, game_number, round_number)
        )
    """)
    
    con.execute("""
        CREATE TABLE IF NOT EXISTS captions (
            session_id VARCHAR,
            game_number INT,
            round_number INT,
            player_id VARCHAR,
            caption VARCHAR,
            score INT,
            roast_comment VARCHAR,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (session_id, game_number, round_number, player_id)
        )
    """)


def generate_session_id() -> str:
    """Generate a short, unique session ID (6 alphanumeric chars)."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


# --- Session Management ---

def create_session(total_rounds: int = 5, round_timer: int = 45) -> str:
    """Create a new game session and return the session ID."""
    con = get_connection()
    session_id = generate_session_id()
    
    # Ensure uniqueness (unlikely collision, but be safe)
    while session_exists(session_id):
        session_id = generate_session_id()
    
    con.execute("""
        INSERT INTO sessions (session_id, total_rounds, round_timer_seconds)
        VALUES (?, ?, ?)
    """, [session_id, total_rounds, round_timer])
    
    return session_id


def session_exists(session_id: str) -> bool:
    """Check if a session exists."""
    con = get_connection()
    result = con.execute(
        "SELECT 1 FROM sessions WHERE session_id = ?", [session_id]
    ).fetchone()
    return result is not None


def get_session(session_id: str) -> Optional[dict]:
    """Get session details."""
    con = get_connection()
    result = con.execute("""
        SELECT session_id, status, current_round, current_game, total_rounds, round_timer_seconds, created_at
        FROM sessions WHERE session_id = ?
    """, [session_id]).fetchone()
    
    if result:
        return {
            'session_id': result[0],
            'status': result[1],
            'current_round': result[2],
            'current_game': result[3],
            'total_rounds': result[4],
            'round_timer_seconds': result[5],
            'created_at': result[6]
        }
    return None


def update_session_status(session_id: str, status: str) -> None:
    """Update session status (lobby, playing, game_over, finished)."""
    con = get_connection()
    con.execute(
        "UPDATE sessions SET status = ? WHERE session_id = ?",
        [status, session_id]
    )


def increment_round(session_id: str) -> int:
    """Increment current round and return new round number."""
    con = get_connection()
    con.execute(
        "UPDATE sessions SET current_round = current_round + 1 WHERE session_id = ?",
        [session_id]
    )
    result = con.execute(
        "SELECT current_round FROM sessions WHERE session_id = ?",
        [session_id]
    ).fetchone()
    return result[0] if result else 0


def start_new_game(session_id: str) -> int:
    """Start a new game within the same session. Returns new game number."""
    con = get_connection()
    con.execute("""
        UPDATE sessions 
        SET current_game = current_game + 1, current_round = 0, status = 'lobby'
        WHERE session_id = ?
    """, [session_id])
    result = con.execute(
        "SELECT current_game FROM sessions WHERE session_id = ?",
        [session_id]
    ).fetchone()
    return result[0] if result else 1


def reset_session(session_id: str) -> None:
    """Reset a session completely (clears all games, keeps players)."""
    con = get_connection()
    con.execute("""
        UPDATE sessions SET status = 'lobby', current_round = 0, current_game = 1
        WHERE session_id = ?
    """, [session_id])
    con.execute("DELETE FROM rounds WHERE session_id = ?", [session_id])
    con.execute("DELETE FROM captions WHERE session_id = ?", [session_id])


# --- Player Management ---

def add_player(session_id: str, player_name: str, is_host: bool = False) -> str:
    """Add a player to a session and return their player_id."""
    con = get_connection()
    player_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    
    con.execute("""
        INSERT INTO players (session_id, player_id, name, is_host)
        VALUES (?, ?, ?, ?)
    """, [session_id, player_id, player_name.strip() or "Anonymous", is_host])
    
    return player_id


def get_players(session_id: str) -> list[dict]:
    """Get all players in a session."""
    con = get_connection()
    results = con.execute("""
        SELECT player_id, name, is_host, joined_at
        FROM players WHERE session_id = ?
        ORDER BY is_host DESC, joined_at
    """, [session_id]).fetchall()
    
    return [
        {'player_id': r[0], 'name': r[1], 'is_host': r[2], 'joined_at': r[3]}
        for r in results
    ]


def get_player_name(session_id: str, player_id: str) -> Optional[str]:
    """Get a player's name."""
    con = get_connection()
    result = con.execute("""
        SELECT name FROM players
        WHERE session_id = ? AND player_id = ?
    """, [session_id, player_id]).fetchone()
    return result[0] if result else None


def get_host_player(session_id: str) -> Optional[dict]:
    """Get the host player for a session."""
    con = get_connection()
    result = con.execute("""
        SELECT player_id, name FROM players
        WHERE session_id = ? AND is_host = TRUE
    """, [session_id]).fetchone()
    if result:
        return {'player_id': result[0], 'name': result[1]}
    return None


# --- Round Management ---

def start_round(session_id: str, game_number: int, round_number: int, image_url: str) -> None:
    """Record the start of a new round."""
    con = get_connection()
    con.execute("""
        INSERT INTO rounds (session_id, game_number, round_number, image_url, started_at)
        VALUES (?, ?, ?, ?, ?)
    """, [session_id, game_number, round_number, image_url, datetime.now()])


def end_round(session_id: str, game_number: int, round_number: int) -> None:
    """Mark a round as ended."""
    con = get_connection()
    con.execute("""
        UPDATE rounds SET ended_at = ?
        WHERE session_id = ? AND game_number = ? AND round_number = ?
    """, [datetime.now(), session_id, game_number, round_number])


def get_round_image(session_id: str, game_number: int, round_number: int) -> Optional[str]:
    """Get the image URL for a round."""
    con = get_connection()
    result = con.execute("""
        SELECT image_url FROM rounds
        WHERE session_id = ? AND game_number = ? AND round_number = ?
    """, [session_id, game_number, round_number]).fetchone()
    return result[0] if result else None


# --- Caption Management ---

def submit_caption(
    session_id: str,
    game_number: int,
    round_number: int,
    player_id: str,
    caption: str
) -> bool:
    """Submit a caption. Returns True if successful, False if already submitted."""
    con = get_connection()
    
    # Check if player already submitted this round
    existing = con.execute("""
        SELECT 1 FROM captions
        WHERE session_id = ? AND game_number = ? AND round_number = ? AND player_id = ?
    """, [session_id, game_number, round_number, player_id]).fetchone()
    
    if existing:
        return False
    
    # Enforce 15 word limit
    words = caption.strip().split()
    if len(words) > 15:
        caption = ' '.join(words[:15])
    
    con.execute("""
        INSERT INTO captions (session_id, game_number, round_number, player_id, caption)
        VALUES (?, ?, ?, ?, ?)
    """, [session_id, game_number, round_number, player_id, caption.strip()])
    
    return True


def has_submitted(session_id: str, game_number: int, round_number: int, player_id: str) -> bool:
    """Check if a player has submitted a caption this round."""
    con = get_connection()
    result = con.execute("""
        SELECT 1 FROM captions
        WHERE session_id = ? AND game_number = ? AND round_number = ? AND player_id = ?
    """, [session_id, game_number, round_number, player_id]).fetchone()
    return result is not None


def get_round_captions(session_id: str, game_number: int, round_number: int) -> list[dict]:
    """Get all captions for a round with player names."""
    con = get_connection()
    results = con.execute("""
        SELECT c.player_id, p.name, c.caption, c.score, c.roast_comment
        FROM captions c
        JOIN players p ON c.session_id = p.session_id AND c.player_id = p.player_id
        WHERE c.session_id = ? AND c.game_number = ? AND c.round_number = ?
        ORDER BY c.score DESC NULLS LAST
    """, [session_id, game_number, round_number]).fetchall()
    
    return [
        {
            'player_id': r[0],
            'player_name': r[1],
            'caption': r[2],
            'score': r[3],
            'roast_comment': r[4]
        }
        for r in results
    ]


def update_caption_scores(
    session_id: str,
    game_number: int,
    round_number: int,
    scores: list[dict]
) -> None:
    """Update scores and roast comments for captions.
    
    scores: list of {'player_name': str, 'score': int, 'roast_comment': str}
    """
    con = get_connection()
    
    for score_data in scores:
        # Find player_id by name
        player = con.execute("""
            SELECT player_id FROM players
            WHERE session_id = ? AND name = ?
        """, [session_id, score_data.get('player_name', '')]).fetchone()
        
        if player:
            con.execute("""
                UPDATE captions
                SET score = ?, roast_comment = ?
                WHERE session_id = ? AND game_number = ? AND round_number = ? AND player_id = ?
            """, [
                score_data.get('score', 0),
                score_data.get('roast_comment', ''),
                session_id,
                game_number,
                round_number,
                player[0]
            ])


# --- Scoreboard ---

def get_game_scoreboard(session_id: str, game_number: int) -> list[dict]:
    """Get the scoreboard for a specific game (total points per player in that game)."""
    con = get_connection()
    results = con.execute("""
        SELECT p.name, COALESCE(SUM(c.score), 0) as total_score
        FROM players p
        LEFT JOIN captions c ON p.session_id = c.session_id 
            AND p.player_id = c.player_id 
            AND c.game_number = ?
        WHERE p.session_id = ?
        GROUP BY p.player_id, p.name
        ORDER BY total_score DESC
    """, [game_number, session_id]).fetchall()
    
    return [
        {'name': r[0], 'total_score': r[1], 'rank': i + 1}
        for i, r in enumerate(results)
    ]


def get_session_scoreboard(session_id: str) -> list[dict]:
    """Get the running scoreboard for current game in session."""
    session = get_session(session_id)
    if not session:
        return []
    return get_game_scoreboard(session_id, session['current_game'])


def get_round_winner(session_id: str, game_number: int, round_number: int) -> Optional[dict]:
    """Get the winner of a specific round."""
    con = get_connection()
    result = con.execute("""
        SELECT p.name, c.caption, c.score, c.roast_comment
        FROM captions c
        JOIN players p ON c.session_id = p.session_id AND c.player_id = p.player_id
        WHERE c.session_id = ? AND c.game_number = ? AND c.round_number = ?
        ORDER BY c.score DESC
        LIMIT 1
    """, [session_id, game_number, round_number]).fetchone()
    
    if result:
        return {
            'name': result[0],
            'caption': result[1],
            'score': result[2],
            'roast_comment': result[3]
        }
    return None


def get_game_winner(session_id: str, game_number: Optional[int] = None) -> Optional[dict]:
    """Get the overall game winner."""
    if game_number is None:
        session = get_session(session_id)
        if not session:
            return None
        game_number = session['current_game']
    
    scoreboard = get_game_scoreboard(session_id, game_number)
    if scoreboard:
        return scoreboard[0]
    return None
