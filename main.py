"""
Cat Caption Cage Match - Main Application

An AI-powered party game where players write meme captions for random cat
pictures and have them judged by Gemini. Designed for remote teams as a
quick icebreaker game.

Run with: python main.py
"""

import os
import time
import threading
from datetime import datetime
from typing import Optional

import gradio as gr

# Load environment variables from .env file (optional dependency)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed - that's okay, env vars can be set directly
    pass

# Import our modules
import storage
import images
import llm


# --- Configuration ---
DEFAULT_ROUNDS = int(os.environ.get("ROUNDS_PER_GAME", "5"))
DEFAULT_TIMER = int(os.environ.get("ROUND_TIMER_SECONDS", "120"))
MAX_CAPTION_WORDS = 15


# --- Session State (per-session data not in DB) ---
# This holds ephemeral state like current image and timer
class SessionState:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.current_image = None
        self.current_image_url = None
        self.round_start_time: Optional[float] = None
        self.round_timer_seconds = DEFAULT_TIMER
        self.submissions_this_round: set = set()  # player_ids who submitted


_session_states: dict[str, SessionState] = {}


def get_session_state(session_id: str) -> Optional[SessionState]:
    """Get or create session state."""
    if session_id not in _session_states:
        if storage.session_exists(session_id):
            _session_states[session_id] = SessionState(session_id)
            session = storage.get_session(session_id)
            if session:
                _session_states[session_id].round_timer_seconds = session['round_timer_seconds']
    return _session_states.get(session_id)


# --- Game Logic ---

def create_new_session(host_name: str) -> tuple[str, str, str]:
    """
    Create a new game session with host as first player.
    Returns (session_id, join_url, host_player_id).
    """
    session_id = storage.create_session(
        total_rounds=DEFAULT_ROUNDS,
        round_timer=DEFAULT_TIMER
    )
    _session_states[session_id] = SessionState(session_id)
    
    # Add host as first player
    host_name = host_name.strip() or "Host"
    host_player_id = storage.add_player(session_id, host_name, is_host=True)
    
    # In production, this would be the actual URL
    join_url = f"Session Code: {session_id}"
    
    return session_id, join_url, host_player_id


def join_session(session_id: str, player_name: str) -> tuple[bool, str, str]:
    """
    Join an existing session.
    Returns (success, message, player_id).
    """
    session_id = session_id.strip().upper()
    
    if not storage.session_exists(session_id):
        return False, f"Session '{session_id}' not found. Check the code and try again.", ""
    
    session = storage.get_session(session_id)
    if session and session['status'] == 'finished':
        return False, "This session has ended.", ""
    
    player_name = player_name.strip() or "Anonymous"
    player_id = storage.add_player(session_id, player_name, is_host=False)
    
    # Ensure session state exists
    get_session_state(session_id)
    
    return True, f"Welcome, {player_name}! Waiting for host to start the round...", player_id


def start_round(session_id: str) -> tuple[bool, str, Optional[object]]:
    """
    Start a new round. Host-only action.
    Returns (success, message, image).
    """
    session = storage.get_session(session_id)
    if not session:
        return False, "Session not found.", None
    
    # Check if game is over (all rounds completed)
    if session['current_round'] >= session['total_rounds']:
        storage.update_session_status(session_id, 'game_over')
        return False, "Game is over! All rounds completed. Start a new game to continue.", None
    
    # Get session state
    state = get_session_state(session_id)
    if not state:
        return False, "Session state error.", None
    
    # Increment round
    round_num = storage.increment_round(session_id)
    game_num = session['current_game']
    
    # Fetch new cat image
    image, image_url = images.fetch_random_cat()
    state.current_image = image
    state.current_image_url = image_url
    state.round_start_time = time.time()
    state.submissions_this_round = set()
    
    # Record round in DB
    storage.start_round(session_id, game_num, round_num, image_url)
    storage.update_session_status(session_id, 'playing')
    
    return True, f"Round {round_num} of {session['total_rounds']} started! You have {state.round_timer_seconds} seconds.", image


def submit_caption(
    session_id: str,
    player_id: str,
    caption: str
) -> tuple[bool, str]:
    """
    Submit a caption for the current round.
    Returns (success, message).
    """
    session = storage.get_session(session_id)
    if not session:
        return False, "Session not found."
    
    if session['status'] != 'playing':
        return False, "No round in progress."
    
    state = get_session_state(session_id)
    if not state:
        return False, "Session state error."
    
    # Check timer
    if state.round_start_time:
        elapsed = time.time() - state.round_start_time
        if elapsed > state.round_timer_seconds:
            return False, "⏰ Too late! Time's up for this round."
    
    # Check if already submitted
    if player_id in state.submissions_this_round:
        return False, "You've already submitted a caption this round!"
    
    game_num = session['current_game']
    round_num = session['current_round']
    
    # Enforce word limit
    words = caption.strip().split()
    if len(words) > MAX_CAPTION_WORDS:
        return False, f"Caption too long! Maximum {MAX_CAPTION_WORDS} words."
    
    if len(words) == 0:
        return False, "Please enter a caption."
    
    # Submit
    success = storage.submit_caption(session_id, game_num, round_num, player_id, caption)
    if success:
        state.submissions_this_round.add(player_id)
        return True, "✅ Caption submitted! Waiting for other players..."
    else:
        return False, "You've already submitted a caption this round!"


def end_round_and_score(session_id: str) -> tuple[bool, str, list[dict], bool]:
    """
    End the current round and score all captions.
    Returns (success, message, results, is_game_over).
    """
    session = storage.get_session(session_id)
    if not session:
        return False, "Session not found.", [], False
    
    if session['status'] != 'playing':
        return False, "No round in progress.", [], False
    
    state = get_session_state(session_id)
    if not state:
        return False, "Session state error.", [], False
    
    game_num = session['current_game']
    round_num = session['current_round']
    
    # Get all captions for this round
    captions = storage.get_round_captions(session_id, game_num, round_num)
    
    if not captions:
        return False, "No captions submitted this round!", [], False
    
    # Prepare for LLM scoring
    caption_data = [
        {'player_name': c['player_name'], 'caption': c['caption']}
        for c in captions
    ]
    
    # Score with LLM
    scored_results = llm.score_captions(
        state.current_image,
        caption_data,
        images.describe_image_for_llm(state.current_image) if state.current_image else None
    )
    
    # Update scores in DB
    storage.update_caption_scores(session_id, game_num, round_num, scored_results)
    storage.end_round(session_id, game_num, round_num)
    
    # Check if game is over (all rounds completed)
    is_game_over = round_num >= session['total_rounds']
    
    if is_game_over:
        storage.update_session_status(session_id, 'game_over')
    else:
        storage.update_session_status(session_id, 'lobby')
    
    return True, f"Round {round_num} complete!", scored_results, is_game_over


def start_new_game(session_id: str) -> tuple[bool, str, int]:
    """
    Start a new game within the same session.
    Returns (success, message, new_game_number).
    """
    session = storage.get_session(session_id)
    if not session:
        return False, "Session not found.", 0
    
    new_game_num = storage.start_new_game(session_id)
    
    # Reset session state
    state = get_session_state(session_id)
    if state:
        state.current_image = None
        state.current_image_url = None
        state.round_start_time = None
        state.submissions_this_round = set()
    
    return True, f"🎮 Game {new_game_num} started! Ready for round 1.", new_game_num


def get_time_remaining(session_id: str) -> int:
    """Get seconds remaining in current round."""
    state = get_session_state(session_id)
    if not state or not state.round_start_time:
        return 0
    
    elapsed = time.time() - state.round_start_time
    remaining = state.round_timer_seconds - elapsed
    return max(0, int(remaining))


def format_scoreboard(session_id: str) -> str:
    """Format the scoreboard as markdown."""
    session = storage.get_session(session_id)
    if not session:
        return "_No scores yet_"
    
    scoreboard = storage.get_game_scoreboard(session_id, session['current_game'])
    if not scoreboard:
        return "_No scores yet_"
    
    lines = [f"### 🏆 Game {session['current_game']} Scoreboard", ""]
    for entry in scoreboard:
        medal = ""
        if entry['rank'] == 1:
            medal = "🥇 "
        elif entry['rank'] == 2:
            medal = "🥈 "
        elif entry['rank'] == 3:
            medal = "🥉 "
        
        lines.append(f"{medal}**{entry['name']}** — {entry['total_score']} pts")
    
    return "\n".join(lines)


def format_round_results(results: list[dict], round_num: int) -> str:
    """Format round results as markdown."""
    if not results:
        return "_No results_"
    
    # Sort by score descending
    sorted_results = sorted(results, key=lambda x: x.get('score', 0), reverse=True)
    
    lines = [f"### 🎯 Round {round_num} Results", ""]
    
    for i, r in enumerate(sorted_results):
        score = r.get('score', 0)
        name = r.get('player_name', 'Unknown')
        caption = r.get('caption', '')
        roast = r.get('roast_comment', '')
        
        winner_badge = " 👑" if i == 0 else ""
        
        lines.append(f"**{name}**{winner_badge} — {score}/10")
        lines.append(f"> \"{caption}\"")
        if roast:
            lines.append(f"> _🔥 {roast}_")
        lines.append("")
    
    return "\n".join(lines)


def format_game_over(session_id: str) -> str:
    """Format game over screen with winner."""
    session = storage.get_session(session_id)
    if not session:
        return "### Game Over!\n\n_No winner determined._"
    
    winner = storage.get_game_winner(session_id, session['current_game'])
    scoreboard = storage.get_game_scoreboard(session_id, session['current_game'])
    
    if not winner:
        return "### Game Over!\n\n_No winner determined._"
    
    lines = [
        "# 🎉 GAME OVER! 🎉",
        "",
        f"## 👑 {winner['name']} is the Supreme Cat Meme Champion! 👑",
        f"### Final Score: {winner['total_score']} points",
        "",
        f"_Game {session['current_game']} complete!_",
        "",
        "---",
        "",
        "### Final Standings:",
        ""
    ]
    
    for entry in scoreboard:
        medal = ""
        if entry['rank'] == 1:
            medal = "🥇 "
        elif entry['rank'] == 2:
            medal = "🥈 "
        elif entry['rank'] == 3:
            medal = "🥉 "
        
        lines.append(f"{medal}**{entry['name']}** — {entry['total_score']} pts")
    
    return "\n".join(lines)


# --- Gradio UI ---

def build_host_ui():
    """Build the host/admin UI - host is also a player."""
    
    # State
    session_id_state = gr.State(value=None)
    host_player_id_state = gr.State(value=None)
    
    with gr.Blocks(title="Cat Caption Cage Match - Host", theme=gr.themes.Soft()) as host_ui:
        gr.Markdown("# 🐱 Cat Caption Cage Match — Host Dashboard")
        
        # Session creation section (visible initially)
        with gr.Group() as create_session_group:
            gr.Markdown("### Start a New Session")
            gr.Markdown("_Enter your name to create a session. You'll be the host AND a player!_")
            host_name_input = gr.Textbox(
                label="Your Name",
                placeholder="Enter your display name",
                max_lines=1
            )
            create_btn = gr.Button("🎮 Start New Session", variant="primary", size="lg")
            create_status = gr.Markdown("")
        
        # Main game section (hidden until session created)
        with gr.Group(visible=False) as game_section:
            session_info = gr.Markdown("")
            session_code_display = gr.Textbox(
                label="📋 Session Code (share with players)",
                interactive=False
            )
            
            with gr.Row():
                with gr.Column(scale=2):
                    # Round controls
                    with gr.Group():
                        gr.Markdown("### Round Controls")
                        with gr.Row():
                            start_round_btn = gr.Button("▶️ Start Round", variant="primary")
                            end_round_btn = gr.Button("⏹️ End Round & Score", variant="secondary")
                        timer_display = gr.Markdown("_Click 'Start Round' to begin_")
                        round_status = gr.Markdown("")
                    
                    # Cat image and host's caption input
                    cat_image = gr.Image(label="Current Cat", visible=False)
                    
                    with gr.Group() as caption_group:
                        gr.Markdown("### 📝 Your Caption")
                        with gr.Row():
                            host_caption_input = gr.Textbox(
                                label=f"Your Caption (max {MAX_CAPTION_WORDS} words)",
                                placeholder="Write your funniest caption...",
                                max_lines=2,
                                interactive=True
                            )
                            host_submit_btn = gr.Button("📤 Submit", variant="primary")
                        host_caption_status = gr.Markdown("")
                
                with gr.Column(scale=1):
                    # Player list
                    gr.Markdown("### 👥 Players")
                    player_list = gr.Markdown("_No players yet_")
                    refresh_players_btn = gr.Button("🔄 Refresh Players")
                    
                    # Scoreboard
                    scoreboard_display = gr.Markdown("_Scoreboard will appear here_")
            
            # Results section
            with gr.Group():
                gr.Markdown("### 📊 Results")
                results_display = gr.Markdown("")
            
            # Game over / New game section
            with gr.Group(visible=False) as game_over_group:
                game_over_display = gr.Markdown("")
                new_game_btn = gr.Button("🎮 Start New Game (Same Session)", variant="primary", size="lg")
                new_game_status = gr.Markdown("")
            
            # Session controls
            with gr.Row():
                reset_btn = gr.Button("🔄 Reset Everything", variant="secondary")
                end_session_btn = gr.Button("🚪 End Session", variant="stop")
        
        # --- Event handlers ---
        
        def on_create_session(host_name):
            if not host_name.strip():
                return (
                    None, None,
                    gr.update(visible=True),  # keep create section visible
                    gr.update(visible=False),  # hide game section
                    "❌ Please enter your name to start.",
                    "", "", "", "",
                    gr.update(visible=False), gr.update(visible=False),
                    ""
                )
            
            session_id, join_url, host_player_id = create_new_session(host_name)
            
            return (
                session_id,
                host_player_id,
                gr.update(visible=False),  # hide create section
                gr.update(visible=True),   # show game section
                "",  # clear create status
                f"### ✅ Session Created!\n\nYou are **{host_name.strip()}** (Host)\n\nShare the code below with players:",
                session_id,
                format_scoreboard(session_id),
                f"**1 player:**\n\n- {host_name.strip()} 👑 (Host)",
                gr.update(visible=False),  # hide cat image
                gr.update(visible=False),  # hide game over section
                ""
            )
        
        def on_start_round(session_id, host_player_id):
            if not session_id:
                return (
                    gr.update(), "❌ No session active.", "", 
                    format_scoreboard(session_id) if session_id else "",
                    gr.update(visible=False), "", gr.update(interactive=True)
                )
            
            success, msg, image = start_round(session_id)
            if success:
                session = storage.get_session(session_id)
                round_num = session['current_round'] if session else 0
                total_rounds = session['total_rounds'] if session else DEFAULT_ROUNDS
                state = get_session_state(session_id)
                timer_secs = state.round_timer_seconds if state else DEFAULT_TIMER
                
                return (
                    gr.update(value=image, visible=True),
                    f"### Round {round_num} of {total_rounds}\n\n⏱️ {timer_secs} seconds | Submit your caption!",
                    msg,
                    format_scoreboard(session_id),
                    gr.update(visible=False),  # hide game over section
                    "",
                    gr.update(interactive=True)  # enable caption input
                )
            return (
                gr.update(visible=False), msg, "", 
                format_scoreboard(session_id),
                gr.update(visible=False), "", gr.update(interactive=True)
            )
        
        def on_host_submit_caption(session_id, host_player_id, caption):
            if not session_id or not host_player_id:
                return "❌ No session active."
            
            success, message = submit_caption(session_id, host_player_id, caption)
            return message
        
        def on_end_round(session_id):
            if not session_id:
                return (
                    "❌ No session active.", "", 
                    format_scoreboard(session_id) if session_id else "",
                    gr.update(visible=False), ""
                )
            
            session = storage.get_session(session_id)
            round_num = session['current_round'] if session else 0
            
            success, msg, results, is_game_over = end_round_and_score(session_id)
            
            if success:
                if is_game_over:
                    return (
                        "🏁 Game finished! See results below.",
                        format_round_results(results, round_num),
                        format_scoreboard(session_id),
                        gr.update(visible=True),  # show game over section
                        format_game_over(session_id)
                    )
                
                return (
                    f"✅ {msg} Ready for next round.",
                    format_round_results(results, round_num),
                    format_scoreboard(session_id),
                    gr.update(visible=False),
                    ""
                )
            
            return (
                msg, "", format_scoreboard(session_id),
                gr.update(visible=False), ""
            )
        
        def on_new_game(session_id):
            if not session_id:
                return "", gr.update(visible=False), "", format_scoreboard(session_id) if session_id else ""
            
            success, msg, game_num = start_new_game(session_id)
            
            if success:
                return (
                    msg,
                    gr.update(visible=False),  # hide game over section
                    "",  # clear results
                    format_scoreboard(session_id)
                )
            
            return msg, gr.update(visible=True), "", format_scoreboard(session_id)
        
        def on_refresh_players(session_id):
            if not session_id:
                return "_No session active_"
            
            players = storage.get_players(session_id)
            if not players:
                return "_No players yet_"
            
            lines = []
            for p in players:
                host_badge = " 👑 (Host)" if p.get('is_host') else ""
                lines.append(f"- {p['name']}{host_badge}")
            
            return f"**{len(players)} player(s):**\n\n" + "\n".join(lines)
        
        def on_reset_session(session_id):
            if not session_id:
                return "❌ No session active.", "", "", gr.update(visible=False), ""
            
            storage.reset_session(session_id)
            state = get_session_state(session_id)
            if state:
                state.current_image = None
                state.current_image_url = None
                state.round_start_time = None
                state.submissions_this_round = set()
            
            return (
                "✅ Session reset! Players remain, all scores cleared.",
                "",
                format_scoreboard(session_id),
                gr.update(visible=False),
                ""
            )
        
        def on_end_session(session_id):
            if not session_id:
                return "", ""
            
            storage.update_session_status(session_id, 'finished')
            return "🚪 Session ended. Thanks for playing!", format_scoreboard(session_id)
        
        # Connect events
        create_btn.click(
            on_create_session,
            inputs=[host_name_input],
            outputs=[
                session_id_state, host_player_id_state,
                create_session_group, game_section,
                create_status, session_info, session_code_display,
                scoreboard_display, player_list,
                cat_image, game_over_group, game_over_display
            ]
        )
        
        start_round_btn.click(
            on_start_round,
            inputs=[session_id_state, host_player_id_state],
            outputs=[
                cat_image, timer_display, round_status, scoreboard_display,
                game_over_group, game_over_display, host_caption_input
            ]
        )
        
        host_submit_btn.click(
            on_host_submit_caption,
            inputs=[session_id_state, host_player_id_state, host_caption_input],
            outputs=[host_caption_status]
        )
        
        end_round_btn.click(
            on_end_round,
            inputs=[session_id_state],
            outputs=[round_status, results_display, scoreboard_display, game_over_group, game_over_display]
        )
        
        new_game_btn.click(
            on_new_game,
            inputs=[session_id_state],
            outputs=[new_game_status, game_over_group, results_display, scoreboard_display]
        )
        
        refresh_players_btn.click(
            on_refresh_players,
            inputs=[session_id_state],
            outputs=[player_list]
        )
        
        reset_btn.click(
            on_reset_session,
            inputs=[session_id_state],
            outputs=[round_status, results_display, scoreboard_display, game_over_group, game_over_display]
        )
        
        end_session_btn.click(
            on_end_session,
            inputs=[session_id_state],
            outputs=[results_display, scoreboard_display]
        )
    
    return host_ui


def build_player_ui():
    """Build the player UI."""
    
    # State
    session_id_state = gr.State(value=None)
    player_id_state = gr.State(value=None)
    
    with gr.Blocks(title="Cat Caption Cage Match - Player", theme=gr.themes.Soft()) as player_ui:
        gr.Markdown("# 🐱 Cat Caption Cage Match")
        
        # Join section
        with gr.Group() as join_group:
            gr.Markdown("### Join a Game")
            with gr.Row():
                session_code_input = gr.Textbox(
                    label="Session Code",
                    placeholder="Enter 6-character code (e.g., ABC123)",
                    max_lines=1
                )
                player_name_input = gr.Textbox(
                    label="Your Name",
                    placeholder="Enter your display name",
                    max_lines=1
                )
            join_btn = gr.Button("🎮 Join Game", variant="primary")
            join_status = gr.Markdown("")
        
        # Game section (hidden until joined)
        with gr.Group(visible=False) as game_group:
            player_welcome = gr.Markdown("### Welcome!")
            game_status = gr.Markdown("_Waiting for host to start round..._")
            
            # Cat image and caption
            cat_image = gr.Image(label="Caption this cat!", visible=False)
            
            with gr.Row():
                caption_input = gr.Textbox(
                    label=f"Your Caption (max {MAX_CAPTION_WORDS} words)",
                    placeholder="Write your funniest caption...",
                    max_lines=2,
                    interactive=True
                )
                submit_btn = gr.Button("📤 Submit Caption", variant="primary")
            
            caption_status = gr.Markdown("")
            
            # Scoreboard
            gr.Markdown("---")
            scoreboard_display = gr.Markdown("### 🏆 Scoreboard\n_Scores will appear here_")
            
            # Results
            results_display = gr.Markdown("")
            
            # Refresh button
            refresh_btn = gr.Button("🔄 Refresh Game State")
        
        # --- Event handlers ---
        
        def on_join(session_code, player_name):
            success, message, player_id = join_session(session_code, player_name)
            
            if success:
                session_id = session_code.strip().upper()
                return (
                    session_id,
                    player_id,
                    gr.update(visible=False),  # hide join group
                    gr.update(visible=True),   # show game group
                    f"### 👋 Welcome, {player_name.strip() or 'Anonymous'}!",
                    message,
                    format_scoreboard(session_id),
                    ""
                )
            
            return (
                None,
                None,
                gr.update(visible=True),
                gr.update(visible=False),
                "",
                message,
                "",
                ""
            )
        
        def on_submit_caption(session_id, player_id, caption):
            if not session_id or not player_id:
                return "❌ Not in a game session."
            
            success, message = submit_caption(session_id, player_id, caption)
            return message
        
        def on_refresh(session_id, player_id):
            if not session_id:
                return (
                    "_Not in a game_",
                    gr.update(visible=False),
                    "_No scores yet_",
                    "",
                    gr.update(interactive=True)
                )
            
            session = storage.get_session(session_id)
            if not session:
                return (
                    "_Session not found_",
                    gr.update(visible=False),
                    "_No scores yet_",
                    "",
                    gr.update(interactive=True)
                )
            
            state = get_session_state(session_id)
            round_num = session['current_round']
            game_num = session['current_game']
            total_rounds = session['total_rounds']
            
            # Determine status and image
            if session['status'] == 'finished':
                return (
                    "🚪 **Session ended.** Thanks for playing!",
                    gr.update(visible=False),
                    format_scoreboard(session_id),
                    "",
                    gr.update(interactive=False)
                )
            
            if session['status'] == 'game_over':
                return (
                    f"🏁 **Game {game_num} Over!** Waiting for host to start new game...",
                    gr.update(visible=False),
                    format_game_over(session_id),
                    "",
                    gr.update(interactive=False)
                )
            
            if session['status'] == 'playing':
                # Show current round
                time_left = get_time_remaining(session_id)
                has_submitted = player_id in state.submissions_this_round if state else False
                
                status_text = f"**Round {round_num} of {total_rounds}** | ⏱️ {time_left}s remaining"
                if has_submitted:
                    status_text += " | ✅ Caption submitted!"
                
                return (
                    status_text,
                    gr.update(value=state.current_image, visible=True) if state and state.current_image else gr.update(visible=False),
                    format_scoreboard(session_id),
                    "",
                    gr.update(interactive=not has_submitted)
                )
            
            # Lobby status - show last round results if available
            results_md = ""
            if round_num > 0:
                last_results = storage.get_round_captions(session_id, game_num, round_num)
                if last_results:
                    results_md = format_round_results(last_results, round_num)
            
            return (
                f"_Waiting for host to start round {round_num + 1} of {total_rounds}..._",
                gr.update(visible=False),
                format_scoreboard(session_id),
                results_md,
                gr.update(interactive=True)
            )
        
        # Connect events
        join_btn.click(
            on_join,
            inputs=[session_code_input, player_name_input],
            outputs=[
                session_id_state, player_id_state,
                join_group, game_group,
                player_welcome, join_status,
                scoreboard_display, results_display
            ]
        )
        
        submit_btn.click(
            on_submit_caption,
            inputs=[session_id_state, player_id_state, caption_input],
            outputs=[caption_status]
        )
        
        refresh_btn.click(
            on_refresh,
            inputs=[session_id_state, player_id_state],
            outputs=[
                game_status, cat_image,
                scoreboard_display, results_display, caption_input
            ]
        )
    
    return player_ui


def build_app():
    """Build the main application with tabs for host and player."""
    
    with gr.Blocks(
        title="Cat Caption Cage Match",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container { max-width: 1200px; margin: auto; }
        """
    ) as app:
        gr.Markdown("""
        # 🐱 Cat Caption Cage Match
        
        *An AI-powered party game for remote teams*
        
        **How to play:**
        1. **Host:** Go to the "Host" tab, enter your name, and start a session
        2. **Players:** Go to the "Player" tab, enter the session code, and join!
        3. Each round, everyone (including the host!) captions the same cat picture
        4. Gemini AI judges the captions and roasts everyone
        5. After 5 rounds, the champion is crowned! Then start a new game!
        
        ---
        """)
        
        with gr.Tabs():
            with gr.TabItem("🎮 Host"):
                build_host_ui()
            
            with gr.TabItem("👤 Player"):
                build_player_ui()
        
        gr.Markdown("""
        ---
        *Cat Caption Cage Match — Built for fun, powered by cats and AI* 🐈‍⬛
        """)
    
    return app


# --- Main entry point ---

def main():
    """Run the Cat Caption Cage Match application."""
    print("🐱 Starting Cat Caption Cage Match...")
    
    # Initialize LLM
    llm.configure_api()
    
    # Test API connection
    api_ok, api_msg = llm.test_api_connection()
    if api_ok:
        print(f"✅ LLM API: {api_msg}")
    else:
        print(f"⚠️  LLM API: {api_msg}")
        print("   Game will use fake scoring mode.")
    
    # Ensure local cats directory exists
    images.ensure_local_cats_dir()
    
    # Build and launch the app
    app = build_app()
    
    print("\n🚀 Launching web interface...")
    print("   Share the URL with your team to play!\n")
    
    app.launch(
        share=True,  # Creates a public URL for easy sharing
        server_name="0.0.0.0",
        server_port=None,  # Auto-find available port
        show_error=True
    )


if __name__ == "__main__":
    main()
