"""
Cat Caption Cage Match - Main Application

An AI-powered party game where players write meme captions for random cat
pictures and have them judged by Gemini. Designed for remote teams as a
quick icebreaker game.

Run with: python main.py
"""

import os
import time
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
DEFAULT_ROUNDS = int(os.environ.get("ROUNDS_PER_GAME", "3"))
MAX_CAPTION_WORDS = 15


# --- Session State (per-session data not in DB) ---
# This holds ephemeral state like current image
class SessionState:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.current_image = None
        self.current_image_url = None
        self.submissions_this_round: set = set()  # player_ids who submitted
        self.last_player_list_hash: str = ""  # Track changes to avoid flicker


_session_states: dict[str, SessionState] = {}


def get_session_state(session_id: str) -> Optional[SessionState]:
    """Get or create session state."""
    if session_id not in _session_states:
        if storage.session_exists(session_id):
            _session_states[session_id] = SessionState(session_id)
    return _session_states.get(session_id)


# --- Game Logic ---

def create_new_session(host_name: str) -> tuple[str, str, str]:
    """
    Create a new game session with host as first player.
    Returns (session_id, join_url, host_player_id).
    """
    session_id = storage.create_session(
        total_rounds=DEFAULT_ROUNDS,
        round_timer=0  # No timer
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
    state.submissions_this_round = set()
    state.last_player_list_hash = ""  # Reset to force UI update
    
    # Record round in DB
    storage.start_round(session_id, game_num, round_num, image_url)
    storage.update_session_status(session_id, 'playing')
    
    player_count = len(storage.get_players(session_id))
    return True, f"Round {round_num} of {session['total_rounds']} started! Waiting for {player_count} players to submit...", image


def check_all_submitted(session_id: str) -> bool:
    """Check if all players have submitted captions this round."""
    state = get_session_state(session_id)
    if not state:
        return False
    
    players = storage.get_players(session_id)
    total_players = len(players)
    submitted_count = len(state.submissions_this_round)
    
    return submitted_count >= total_players and total_players > 0


def submit_caption(
    session_id: str,
    player_id: str,
    caption: str
) -> tuple[bool, str, bool]:
    """
    Submit a caption for the current round.
    Returns (success, message, all_submitted).
    """
    session = storage.get_session(session_id)
    if not session:
        return False, "Session not found.", False
    
    if session['status'] != 'playing':
        return False, "No round in progress.", False
    
    state = get_session_state(session_id)
    if not state:
        return False, "Session state error.", False
    
    # Check if already submitted
    if player_id in state.submissions_this_round:
        return False, "You've already submitted a caption this round!", False
    
    game_num = session['current_game']
    round_num = session['current_round']
    
    # Enforce word limit
    words = caption.strip().split()
    if len(words) > MAX_CAPTION_WORDS:
        return False, f"Caption too long! Maximum {MAX_CAPTION_WORDS} words.", False
    
    if len(words) == 0:
        return False, "Please enter a caption.", False
    
    # Submit
    success = storage.submit_caption(session_id, game_num, round_num, player_id, caption)
    if success:
        state.submissions_this_round.add(player_id)
        
        # Check if all players have submitted
        all_submitted = check_all_submitted(session_id)
        
        if all_submitted:
            return True, "✅ Caption submitted! All players done - scoring now...", True
        else:
            players = storage.get_players(session_id)
            remaining = len(players) - len(state.submissions_this_round)
            return True, f"✅ Caption submitted! Waiting for {remaining} more player(s)...", False
    else:
        return False, "You've already submitted a caption this round!", False


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
        state.submissions_this_round = set()
        state.last_player_list_hash = ""  # Reset to force UI update
    
    return True, f"🎮 Game {new_game_num} started! Ready for round 1.", new_game_num


def format_player_list(session_id: str, show_submission_status: bool = False) -> str:
    """Format the player list as markdown, optionally showing submission status."""
    if not session_id:
        return "_No session active_"
    
    players = storage.get_players(session_id)
    if not players:
        return "_No players yet_"
    
    state = get_session_state(session_id)
    session = storage.get_session(session_id)
    is_playing = session and session['status'] == 'playing'
    
    lines = []
    for p in players:
        host_badge = " 👑" if p.get('is_host') else ""
        
        # Show checkmark if player has submitted (only during active round)
        if show_submission_status and is_playing and state:
            if p['player_id'] in state.submissions_this_round:
                status = " ✅"
            else:
                status = " ⏳"
        else:
            status = ""
        
        lines.append(f"- {p['name']}{host_badge}{status}")
    
    submitted_count = len(state.submissions_this_round) if state else 0
    total_count = len(players)
    
    if show_submission_status and is_playing:
        header = f"**{submitted_count}/{total_count} submitted:**"
    else:
        header = f"**{total_count} player(s):**"
    
    return header + "\n\n" + "\n".join(lines)


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
                        round_status = gr.Markdown("_Click 'Start Round' to begin_")
                    
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
                    # Player list with submission status (auto-refreshes every 2 seconds)
                    gr.Markdown("### 👥 Players")
                    player_list = gr.Markdown("_No players yet_")
                    refresh_players_btn = gr.Button("🔄 Refresh")
                    
                    # Scoreboard
                    scoreboard_display = gr.Markdown("_Scoreboard will appear here_")
            
            # Auto-refresh timer (every 3 seconds during active session)
            auto_refresh_timer = gr.Timer(value=3, active=False)
            
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
                    "",
                    gr.Timer(active=False)  # keep timer inactive
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
                format_player_list(session_id, show_submission_status=False),
                gr.update(visible=False),  # hide cat image
                gr.update(visible=False),  # hide game over section
                "",
                gr.Timer(active=True)  # activate auto-refresh timer
            )
        
        def on_start_round(session_id, host_player_id):
            if not session_id:
                return (
                    gr.update(), "",
                    format_player_list(session_id, show_submission_status=True) if session_id else "_No players_",
                    format_scoreboard(session_id) if session_id else "",
                    gr.update(visible=False), "",
                    gr.update(value="", interactive=True),  # clear and enable caption input
                    "",  # clear caption status
                    gr.Timer(active=False)
                )

            success, msg, image = start_round(session_id)
            if success:
                session = storage.get_session(session_id)
                round_num = session['current_round'] if session else 0
                total_rounds = session['total_rounds'] if session else DEFAULT_ROUNDS

                return (
                    gr.update(value=image, visible=True),
                    f"### Round {round_num} of {total_rounds}\n\n{msg}",
                    format_player_list(session_id, show_submission_status=True),
                    format_scoreboard(session_id),
                    gr.update(visible=False),  # hide game over section
                    "",
                    gr.update(value="", interactive=True),  # clear and enable caption input
                    "",  # clear caption status
                    gr.Timer(active=True)  # REACTIVATE timer for round updates
                )
            return (
                gr.update(visible=False), msg,
                format_player_list(session_id, show_submission_status=False),
                format_scoreboard(session_id),
                gr.update(visible=False), "",
                gr.update(value="", interactive=True),  # clear caption input
                "",  # clear caption status
                gr.Timer(active=False)
            )
        
        def on_host_submit_caption(session_id, host_player_id, caption):
            if not session_id or not host_player_id:
                return "❌ No session active.", format_player_list(session_id, show_submission_status=True), "", "", gr.update(), "", gr.Timer(active=False)
            
            success, message, all_submitted = submit_caption(session_id, host_player_id, caption)
            
            # If all players submitted, auto-score
            if all_submitted:
                score_success, score_msg, results, is_game_over = end_round_and_score(session_id)
                session = storage.get_session(session_id)
                round_num = session['current_round'] if session else 0
                
                if score_success:
                    if is_game_over:
                        return (
                            message,
                            format_player_list(session_id, show_submission_status=False),
                            format_round_results(results, round_num),
                            format_scoreboard(session_id),
                            gr.update(visible=True),
                            format_game_over(session_id),
                            gr.Timer(active=False)  # Stop timer - game over
                        )
                    return (
                        message,
                        format_player_list(session_id, show_submission_status=False),
                        format_round_results(results, round_num),
                        format_scoreboard(session_id),
                        gr.update(visible=False),
                        "",
                        gr.Timer(active=False)  # Stop timer - round ended, waiting for next
                    )
            
            return (
                message,
                format_player_list(session_id, show_submission_status=True),
                "",
                format_scoreboard(session_id),
                gr.update(),
                "",
                gr.Timer(active=True)  # FIX: Reactivate timer to poll for round completion
            )
        
        def on_end_round(session_id):
            if not session_id:
                return (
                    "❌ No session active.", 
                    format_player_list(session_id, show_submission_status=False),
                    "",
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
                        format_player_list(session_id, show_submission_status=False),
                        format_round_results(results, round_num),
                        format_scoreboard(session_id),
                        gr.update(visible=True),  # show game over section
                        format_game_over(session_id)
                    )
                
                return (
                    f"✅ {msg} Ready for next round.",
                    format_player_list(session_id, show_submission_status=False),
                    format_round_results(results, round_num),
                    format_scoreboard(session_id),
                    gr.update(visible=False),
                    ""
                )
            
            return (
                msg,
                format_player_list(session_id, show_submission_status=True),
                "",
                format_scoreboard(session_id),
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
            session = storage.get_session(session_id) if session_id else None
            is_playing = session and session['status'] == 'playing'
            return format_player_list(session_id, show_submission_status=is_playing)
        
        def on_reset_session(session_id):
            if not session_id:
                return "❌ No session active.", "", "", "", gr.update(visible=False), ""
            
            storage.reset_session(session_id)
            state = get_session_state(session_id)
            if state:
                state.current_image = None
                state.current_image_url = None
                state.submissions_this_round = set()
            
            return (
                "✅ Session reset! Players remain, all scores cleared.",
                format_player_list(session_id, show_submission_status=False),
                "",
                format_scoreboard(session_id),
                gr.update(visible=False),
                ""
            )
        
        def on_end_session(session_id):
            if session_id:
                storage.update_session_status(session_id, 'finished')
            
            # Reset UI to initial state
            return (
                None,  # clear session_id_state
                None,  # clear host_player_id_state
                gr.update(visible=True),   # show create_session_group
                gr.update(visible=False),  # hide game_section
                "",  # clear create_status
                gr.Timer(active=False)  # deactivate timer
            )
        
        def on_auto_refresh(session_id):
            """Auto-refresh for host - updates player list and checks if all submitted.

            Stops timer in stable states to prevent UI flicker from Gradio's timer tick.
            """
            if not session_id:
                return tuple(gr.update() for _ in range(5)) + (gr.Timer(active=False),)

            session = storage.get_session(session_id)
            if not session:
                return tuple(gr.update() for _ in range(5)) + (gr.Timer(active=False),)

            status = session['status']

            # For non-playing states, show results then stop timer
            if status != 'playing':
                # Fetch and display results for completed rounds
                round_num = session['current_round']
                game_num = session['current_game']
                results = storage.get_round_captions(session_id, game_num, round_num)
                results_md = format_round_results(results, round_num) if results else ""
                
                if status == 'game_over':
                    return (
                        format_player_list(session_id, show_submission_status=False),
                        format_scoreboard(session_id),
                        results_md,
                        gr.update(visible=True),
                        format_game_over(session_id),
                        gr.Timer(active=False)
                    )
                # lobby status
                return (
                    format_player_list(session_id, show_submission_status=False),
                    format_scoreboard(session_id),
                    results_md,
                    gr.update(visible=False),
                    "",
                    gr.Timer(active=False)
                )

            # Check if all submitted and auto-end the round
            if check_all_submitted(session_id):
                score_success, score_msg, results, is_game_over = end_round_and_score(session_id)
                round_num = session['current_round']

                if score_success:
                    results_md = format_round_results(results, round_num)
                    if is_game_over:
                        return (
                            format_player_list(session_id, show_submission_status=False),
                            format_scoreboard(session_id),
                            results_md,
                            gr.update(visible=True),
                            format_game_over(session_id),
                            gr.Timer(active=False)
                        )
                    return (
                        format_player_list(session_id, show_submission_status=False),
                        format_scoreboard(session_id),
                        results_md,
                        gr.update(visible=False),
                        "",
                        gr.Timer(active=False)
                    )

            # Active round - only update player list if changed
            state = get_session_state(session_id)
            new_player_list = format_player_list(session_id, show_submission_status=True)

            if state and new_player_list != state.last_player_list_hash:
                state.last_player_list_hash = new_player_list
                return (
                    new_player_list,
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.Timer(active=True)
                )
            
            # No changes during playing - stop timer to prevent flicker
            return tuple(gr.update() for _ in range(5)) + (gr.Timer(active=False),)
        
        # Connect events
        create_btn.click(
            on_create_session,
            inputs=[host_name_input],
            outputs=[
                session_id_state, host_player_id_state,
                create_session_group, game_section,
                create_status, session_info, session_code_display,
                scoreboard_display, player_list,
                cat_image, game_over_group, game_over_display,
                auto_refresh_timer
            ]
        )
        
        # Auto-refresh timer for live updates
        auto_refresh_timer.tick(
            on_auto_refresh,
            inputs=[session_id_state],
            outputs=[player_list, scoreboard_display, results_display, game_over_group, game_over_display, auto_refresh_timer]
        )
        
        start_round_btn.click(
            on_start_round,
            inputs=[session_id_state, host_player_id_state],
            outputs=[
                cat_image, round_status, player_list, scoreboard_display,
                game_over_group, game_over_display, host_caption_input, host_caption_status,
                auto_refresh_timer  # Reactivate timer when round starts
            ]
        )
        
        host_submit_btn.click(
            on_host_submit_caption,
            inputs=[session_id_state, host_player_id_state, host_caption_input],
            outputs=[host_caption_status, player_list, results_display, scoreboard_display, game_over_group, game_over_display, auto_refresh_timer]
        )
        
        end_round_btn.click(
            on_end_round,
            inputs=[session_id_state],
            outputs=[round_status, player_list, results_display, scoreboard_display, game_over_group, game_over_display]
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
            outputs=[round_status, player_list, results_display, scoreboard_display, game_over_group, game_over_display]
        )
        
        end_session_btn.click(
            on_end_session,
            inputs=[session_id_state],
            outputs=[
                session_id_state, host_player_id_state,
                create_session_group, game_section,
                create_status, auto_refresh_timer
            ]
        )
    
    return host_ui


def build_player_ui():
    """Build the player UI."""
    
    # State
    session_id_state = gr.State(value=None)
    player_id_state = gr.State(value=None)
    last_status_state = gr.State(value="")  # Track last status to detect changes
    
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
            with gr.Row():
                with gr.Column(scale=2):
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
                    
                    # Results
                    results_display = gr.Markdown("")
                
                with gr.Column(scale=1):
                    # Player list with submission status
                    gr.Markdown("### 👥 Players")
                    player_list = gr.Markdown("_No players yet_")
                    
                    # Scoreboard
                    scoreboard_display = gr.Markdown("### 🏆 Scoreboard\n_Scores will appear here_")
            
            # Auto-refresh timer (activates after joining, 3 second interval)
            auto_refresh_timer = gr.Timer(value=3, active=False)
            
            # Refresh button (manual backup)
            refresh_btn = gr.Button("🔄 Refresh Game State")
        
        # --- Event handlers ---
        
        def on_join(session_code, player_name):
            success, message, player_id = join_session(session_code, player_name)
            
            if success:
                session_id = session_code.strip().upper()
                return (
                    session_id,
                    player_id,
                    "",  # initial last_status
                    gr.update(visible=False),  # hide join group
                    gr.update(visible=True),   # show game group
                    f"### 👋 Welcome, {player_name.strip() or 'Anonymous'}!",
                    message,
                    format_player_list(session_id, show_submission_status=False),
                    format_scoreboard(session_id),
                    "",
                    gr.Timer(active=True)  # activate auto-refresh
                )
            
            return (
                None,
                None,
                "",
                gr.update(visible=True),
                gr.update(visible=False),
                "",
                message,
                "",
                "",
                "",
                gr.Timer(active=False)
            )
        
        def on_submit_caption(session_id, player_id, caption):
            if not session_id or not player_id:
                return "❌ Not in a game session.", format_player_list(session_id, show_submission_status=True), "", "", gr.update(), gr.Timer(active=False)
            
            success, message, all_submitted = submit_caption(session_id, player_id, caption)
            
            # If all players submitted, trigger scoring
            if all_submitted:
                score_success, score_msg, results, is_game_over = end_round_and_score(session_id)
                session = storage.get_session(session_id)
                round_num = session['current_round'] if session else 0
                
                if score_success:
                    results_md = format_round_results(results, round_num)
                    if is_game_over:
                        results_md += "\n\n" + format_game_over(session_id)
                    return (
                        "✅ All done! Scoring complete. Check results below!",
                        format_player_list(session_id, show_submission_status=False),
                        format_scoreboard(session_id),
                        results_md,
                        gr.update(interactive=False),
                        gr.Timer(active=False)  # Stop timer - round/game ended
                    )
            
            return (
                message,
                format_player_list(session_id, show_submission_status=True),
                format_scoreboard(session_id),
                "",
                gr.update(interactive=not success),  # Disable input after successful submit
                gr.Timer(active=True)  # Reactivate timer to poll for round completion
            )
        
        def on_player_auto_refresh(session_id, player_id, last_status):
            """Auto-refresh for players - updates when game state changes.
            
            Stops timer in stable states to prevent UI flicker from Gradio's timer tick.
            Players can use the Refresh button to manually check for updates.
            """
            if not session_id:
                return (last_status,) + tuple(gr.update() for _ in range(6)) + (gr.Timer(active=False),)
            
            session = storage.get_session(session_id)
            if not session:
                return (last_status,) + tuple(gr.update() for _ in range(6)) + (gr.Timer(active=False),)
            
            state = get_session_state(session_id)
            round_num = session['current_round']
            game_num = session['current_game']
            total_rounds = session['total_rounds']
            status = session['status']
            
            # Build status key for change detection
            submitted_count = len(state.submissions_this_round) if state else 0
            has_submitted = player_id in state.submissions_this_round if state else False
            current_key = f"{status}|r{round_num}|g{game_num}|s{submitted_count}|h{has_submitted}"
            
            # For stable states (lobby, game_over, finished), update once then STOP timer
            if status in ('lobby', 'game_over', 'finished'):
                if current_key == last_status:
                    return (last_status,) + tuple(gr.update() for _ in range(6)) + (gr.Timer(active=False),)
            
            # For 'playing' status, also stop timer when nothing changed to prevent flicker
            if status == 'playing' and current_key == last_status:
                return (last_status,) + tuple(gr.update() for _ in range(6)) + (gr.Timer(active=False),)
            
            # --- State has changed, update UI ---
            
            if status == 'finished':
                return (
                    current_key,
                    "🚪 **Session ended.** Thanks for playing!",
                    gr.update(visible=False),
                    format_player_list(session_id, show_submission_status=False),
                    format_scoreboard(session_id),
                    "",
                    gr.update(interactive=False),
                    gr.Timer(active=False)  # Stop timer - session ended
                )
            
            if status == 'game_over':
                # Include round results before game over display
                results = storage.get_round_captions(session_id, game_num, round_num)
                results_md = format_round_results(results, round_num) if results else ""
                game_over_md = format_game_over(session_id)
                combined_md = results_md + "\n\n" + game_over_md if results_md else game_over_md
                return (
                    current_key,
                    f"🏁 **Game {game_num} Over!** Waiting for host to start new game...",
                    gr.update(visible=False),
                    format_player_list(session_id, show_submission_status=False),
                    format_scoreboard(session_id),
                    combined_md,
                    gr.update(interactive=False),
                    gr.Timer(active=False)  # Stop timer - will restart when new game begins
                )
            
            if status == 'playing':
                players = storage.get_players(session_id)
                status_text = f"**Round {round_num} of {total_rounds}** | {submitted_count}/{len(players)} submitted"
                if has_submitted:
                    status_text += " | ✅ You're done!"
                
                return (
                    current_key,
                    status_text,
                    gr.update(value=state.current_image, visible=True) if state and state.current_image else gr.update(visible=False),
                    format_player_list(session_id, show_submission_status=True),
                    gr.update(),
                    gr.update(),
                    gr.update(interactive=not has_submitted),
                    gr.Timer(active=True)  # Keep timer active during play
                )
            
            # Lobby status - show results then stop timer
            results_md = ""
            if round_num > 0:
                last_results = storage.get_round_captions(session_id, game_num, round_num)
                if last_results:
                    results_md = format_round_results(last_results, round_num)
            
            return (
                current_key,
                f"✅ Round {round_num} complete! Waiting for host to start round {round_num + 1}...",
                gr.update(visible=False),
                format_player_list(session_id, show_submission_status=False),
                format_scoreboard(session_id),
                results_md,
                gr.update(value="", interactive=True),
                gr.Timer(active=False)  # Stop timer in lobby - will restart when round begins
            )
        
        def on_refresh(session_id, player_id):
            """Manual refresh - also reactivates timer if game is playing."""
            if not session_id:
                return (
                    "_Not in a game_",
                    gr.update(visible=False),
                    "_No players_",
                    "_No scores yet_",
                    "",
                    gr.update(interactive=True),
                    gr.Timer(active=False)
                )
            
            session = storage.get_session(session_id)
            if not session:
                return (
                    "_Session not found_",
                    gr.update(visible=False),
                    "_No players_",
                    "_No scores yet_",
                    "",
                    gr.update(interactive=True),
                    gr.Timer(active=False)
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
                    format_player_list(session_id, show_submission_status=False),
                    format_scoreboard(session_id),
                    "",
                    gr.update(interactive=False),
                    gr.Timer(active=False)
                )
            
            if session['status'] == 'game_over':
                return (
                    f"🏁 **Game {game_num} Over!** Waiting for host to start new game...",
                    gr.update(visible=False),
                    format_player_list(session_id, show_submission_status=False),
                    format_game_over(session_id),
                    "",
                    gr.update(interactive=False),
                    gr.Timer(active=False)
                )
            
            if session['status'] == 'playing':
                # Show current round - REACTIVATE timer for live updates
                has_submitted = player_id in state.submissions_this_round if state else False
                players = storage.get_players(session_id)
                submitted_count = len(state.submissions_this_round) if state else 0
                
                status_text = f"**Round {round_num} of {total_rounds}** | {submitted_count}/{len(players)} submitted"
                if has_submitted:
                    status_text += " | ✅ You're done!"
                
                return (
                    status_text,
                    gr.update(value=state.current_image, visible=True) if state and state.current_image else gr.update(visible=False),
                    format_player_list(session_id, show_submission_status=True),
                    format_scoreboard(session_id),
                    "",
                    gr.update(interactive=not has_submitted),
                    gr.Timer(active=True)  # Reactivate timer during play
                )
            
            # Lobby status (between rounds) - clear caption for next round
            results_md = ""
            if round_num > 0:
                last_results = storage.get_round_captions(session_id, game_num, round_num)
                if last_results:
                    results_md = format_round_results(last_results, round_num)
            
            return (
                f"_Waiting for host to start round {round_num + 1} of {total_rounds}..._",
                gr.update(visible=False),
                format_player_list(session_id, show_submission_status=False),
                format_scoreboard(session_id),
                results_md,
                gr.update(value="", interactive=True),
                gr.Timer(active=False)  # Timer off in lobby
            )
        
        # Connect events
        join_btn.click(
            on_join,
            inputs=[session_code_input, player_name_input],
            outputs=[
                session_id_state, player_id_state, last_status_state,
                join_group, game_group,
                player_welcome, join_status,
                player_list, scoreboard_display, results_display,
                auto_refresh_timer
            ]
        )
        
        # Auto-refresh timer for live updates
        auto_refresh_timer.tick(
            on_player_auto_refresh,
            inputs=[session_id_state, player_id_state, last_status_state],
            outputs=[
                last_status_state,
                game_status, cat_image, player_list,
                scoreboard_display, results_display, caption_input,
                auto_refresh_timer  # Allow function to control timer active state
            ]
        )
        
        submit_btn.click(
            on_submit_caption,
            inputs=[session_id_state, player_id_state, caption_input],
            outputs=[caption_status, player_list, scoreboard_display, results_display, caption_input, auto_refresh_timer]
        )
        
        refresh_btn.click(
            on_refresh,
            inputs=[session_id_state, player_id_state],
            outputs=[
                game_status, cat_image, player_list,
                scoreboard_display, results_display, caption_input,
                auto_refresh_timer  # Allow refresh to reactivate timer
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
        3. Each round, everyone captions the same cat picture
        4. Once ALL players submit, the AI judges and roasts everyone
        5. After 5 rounds, the champion is crowned!
        
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