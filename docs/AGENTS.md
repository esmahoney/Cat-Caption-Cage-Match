# Cat Caption Cage Match - Agent Instructions

## Project Overview

You are an AI coding agent working on **Cat Caption Cage Match**, a Python-based party game for remote teams.

The goal: keep this repo **simple, hackable, and fun**, not enterprise-grade.

---

## What This Game Does

- A host starts a session (entering their name) and shares a join code with players.
- Players join in their browser, see a random cat image, and submit short captions (max 15 words).
- An LLM (Groq or Gemini) scores each caption on humor + creativity (0–10) and provides Gordon Ramsay-style roasts.
- Rounds end automatically when all players have submitted.
- Scores are persisted per session; after 5 rounds, the game declares a winner.
- The host can start another game within the same session.

For now this is a **single-repo, single-service** app. No microservices.

---

## Project Structure

```
Cat-Caption-Cage-Match/
├── main.py              # Main entrypoint - Gradio UI + game flow
├── storage.py           # DuckDB database access (sessions, players, scores)
├── images.py            # Cat image fetching (TheCatAPI + local fallback)
├── llm.py               # LLM scoring + roast mode (Groq/Gemini)
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
├── .gitignore           # Git ignore rules
├── README.md            # User-facing documentation
├── AGENTS.md            # This file - AI agent instructions
├── static/
│   └── cats/            # Local fallback cat images (optional)
└── *.ipynb              # Legacy notebook prototypes (can be ignored)
```

---

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Core entrypoint. Builds Gradio UI with Host and Player tabs. Handles game loop. |
| `storage.py` | All database operations. Uses in-memory DuckDB. Schema: sessions, players, rounds, captions. |
| `images.py` | Fetches random cat images from TheCatAPI. Falls back to local images or placeholder. |
| `llm.py` | Calls Groq (preferred) or Gemini to score captions. Includes `fake_llm` mode for testing without API. |

---

## Setup & Run Commands

### 1. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and add your API keys
```

Required (at least one):
- `GROQ_API_KEY` - Get from https://console.groq.com/keys (recommended)
- `GOOGLE_API_KEY` - Get from https://aistudio.google.com/apikey

Optional:
- `THECATAPI_KEY` - Get from https://thecatapi.com/signup
- `FAKE_LLM_MODE=true` - Use fake scoring (no API needed)

### 4. Run the game

```bash
source .env  # Load environment variables
python main.py
```

This launches a Gradio web interface with a public shareable URL.

---

## Testing Without API Keys

Set `FAKE_LLM_MODE=true` in your `.env` file to run the game with deterministic fake scores. Useful for:
- Local development
- Testing UI changes
- Demos without API costs

---

## Development Guidelines

1. **Keep it simple** - This is a workshop/demo game, not production SaaS.
2. **Small functions** - Each function should do one thing well.
3. **Fail gracefully** - LLM errors should fall back to fake scoring, not crash.
4. **No auth** - Players use ephemeral display names, no accounts.
5. **In-memory DB** - DuckDB runs in-memory; data is lost on restart (by design).

---

## Common Tasks

### Add a new scoring criterion
Edit `llm.py`, update the prompt in `_build_prompt()`.

### Add local cat images
Drop `.jpg` or `.png` files in `static/cats/`. They'll be used as fallbacks.

### Test API connection
```python
from llm import test_api_connection
ok, msg = test_api_connection()
print(ok, msg)
```

---

## Architecture Notes

- **UI Framework:** Gradio (chosen for easy sharing via public URLs)
- **Database:** DuckDB in-memory (schema in `storage.py`)
- **LLM:** Groq (Llama 3.3 70B) preferred, Gemini as fallback
- **Images:** TheCatAPI with local fallback

The game uses Gradio's state management to track session/player IDs per browser tab. All persistent data (scores, players) goes through `storage.py`.

Host UI includes a 2-second auto-refresh timer to keep player list and game state updated.

---

## Non-Goals

- No user authentication or accounts
- No horizontal scaling or multi-instance support
- No real-time WebSocket sync (host uses polling, players refresh manually)
- No image moderation pipeline

These are intentional simplifications for a 2-day build scope.
