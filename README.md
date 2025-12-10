# 🐈‍⬛ Cat Caption Cage Match

_Fastest wins. Laughter guaranteed._

An AI-powered party game where players write meme captions for random cat pictures and have them judged by an LLM (Gemini 2.5 Pro). Designed as a **remote-friendly icebreaker** for Scrum teams, product squads, and any group that needs five minutes of competitive cat chaos.

## Perfect for:

- Remote standups and retros
- PI planning breaks
- Zoom / Meet / Teams socials
- Any meeting that needs less status and more cats

---

## 🎮 How the Game Works

1. **Host starts a session**
   - Open the app and go to the "Host" tab
   - Click **"Start New Session"** to create a unique session code
   - Share the code (e.g., `ABC123`) with your team

2. **Players join**
   - Players go to the "Player" tab
   - Enter the session code and their display name
   - Wait in the lobby for the round to start

3. **Round start**
   - Host clicks **"Start Round"**
   - Everyone sees the **same random cat image**
   - A 45-second timer starts (configurable)

4. **Caption time**
   - Players submit their funniest caption (max **15 words**)
   - One caption per player, per round

5. **AI judgment**
   - Host clicks **"End Round & Score"**
   - The LLM scores each caption from **0–10** on:
     - **Humor**
     - **Relevance to the image**
   - Each caption gets a Gordon Ramsay-style **roast comment** 🔥

6. **Scoreboard & winner**
   - Scores accumulate across rounds
   - After 5 rounds, the player with the most points is crowned **Supreme Cat Meme Champion** 👑

---

## ⚡ Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/your-username/Cat-Caption-Cage-Match.git
cd Cat-Caption-Cage-Match
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```
GOOGLE_API_KEY=your_google_api_key_here
THECATAPI_KEY=your_cat_api_key_here  # optional
```

Get your Google API key at: https://aistudio.google.com/apikey

### 5. Run the game

```bash
python main.py
```

The app will launch and provide:
- A local URL: `http://localhost:7860`
- A public URL: `https://xxxxx.gradio.live` (shareable!)

Share the public URL with your team and start playing!

---

## 🧪 Testing Without API Keys

Don't have a Google API key? No problem! Set fake mode in your `.env`:

```
FAKE_LLM_MODE=true
```

The game will use deterministic fake scores instead of calling the LLM. Great for testing and demos.

---

## 🛠️ Configuration

All configuration is done via environment variables in `.env`:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes* | - | Google Gemini API key |
| `THECATAPI_KEY` | No | - | TheCatAPI key (higher rate limits) |
| `FAKE_LLM_MODE` | No | `false` | Use fake scoring (no API needed) |
| `ROUNDS_PER_GAME` | No | `5` | Number of rounds per game |
| `ROUND_TIMER_SECONDS` | No | `45` | Seconds per round |

*Not required if `FAKE_LLM_MODE=true`

---

## 📁 Project Structure

```
Cat-Caption-Cage-Match/
├── main.py              # Main app - Gradio UI + game flow
├── storage.py           # DuckDB database access
├── images.py            # Cat image fetching
├── llm.py               # LLM scoring + roasts
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
├── .gitignore           # Git ignore rules
├── README.md            # This file
├── AGENTS.md            # AI agent instructions
└── static/cats/         # Local fallback cat images
```

---

## 🧱 Tech Stack

- **Language:** Python 3.10+
- **UI Framework:** [Gradio](https://gradio.app/) - Easy web UIs with public URL sharing
- **LLM:** [Google Gemini](https://ai.google.dev/) 2.5 Pro
- **Images:** [TheCatAPI](https://thecatapi.com) with local fallback
- **Database:** [DuckDB](https://duckdb.org/) (in-memory)

---

## 🐛 Troubleshooting

### "GOOGLE_API_KEY not set"
Make sure you've created a `.env` file with your API key. See step 4 above.

### "TheCatAPI error"
The game will automatically fall back to a generated placeholder image. This is normal if you don't have a TheCatAPI key or have network issues.

### "LLM scoring failed"
The game automatically falls back to fake scoring. Check your API key is valid.

### Players can't see the cat image
Players need to click "Refresh Game State" after the host starts a round. This is a known limitation of the v1 UI.

---

## 🤝 Contributing

This is a simple, hackable party game. PRs welcome for:
- Bug fixes
- UI improvements
- New roast comment styles
- Better mobile support

Keep it simple - this is meant to be a lightweight, fun project!

---

## 📜 License

MIT License - do whatever you want with it, just have fun! 🐱

---

*Built for fun, powered by cats and AI* 🐈‍⬛🎤
