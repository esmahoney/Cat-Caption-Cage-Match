# 🐈‍⬛ Cat Caption Cage Match

_Fastest wins. Laughter guaranteed._

An AI-powered party game where players write meme captions for random cat pictures and have them judged by an LLM. Designed as a **remote-friendly icebreaker** for Scrum teams, product squads, and any group that needs five minutes of competitive cat chaos.

## Perfect for:

- Remote standups and retros
- PI planning breaks
- Zoom / Meet / Teams socials
- Any meeting that needs less status and more cats

---

## 🎮 How the Game Works

1. **Host starts a session**
   - Open the app and go to the "Host" tab
   - Enter your name and click **"Start New Session"**
   - Share the session code (e.g., `ABC123`) with your team

2. **Players join**
   - Players go to the "Player" tab
   - Enter the session code and their display name
   - Wait in the lobby for the round to start

3. **Round start**
   - Host clicks **"Start Round"**
   - Everyone sees the **same random cat image**

4. **Caption time**
   - Players submit their funniest caption (max **15 words**)
   - One caption per player, per round
   - Round ends automatically when all players have submitted

5. **AI judgment**
   - The LLM scores each caption from **0–10** on:
     - **Humor**
     - **Creativity**
   - Each caption gets a Gordon Ramsay-style **roast comment** 🔥

6. **Scoreboard & winner**
   - Scores accumulate across rounds
   - After 5 rounds, the player with the most points is crowned **Supreme Cat Meme Champion** 👑
   - Host can start another game on the same session

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

Edit `.env` and add your API key:

```
# Recommended: Groq (free, fast!)
GROQ_API_KEY=your_groq_api_key_here

# Alternative: Google Gemini
GOOGLE_API_KEY=your_google_api_key_here
```

**Get your API keys:**
- Groq (recommended): https://console.groq.com/keys
- Google Gemini: https://aistudio.google.com/apikey

### 5. Run the game

```bash
source .env  # Load environment variables
python main.py
```

The app will launch and provide:
- A local URL: `http://localhost:7860`
- A public URL: `https://xxxxx.gradio.live` (shareable!)

Share the public URL with your team and start playing!

---

## 🧪 Testing Without API Keys

Don't have an API key? No problem! Set fake mode in your `.env`:

```
FAKE_LLM_MODE=true
```

The game will use deterministic fake scores instead of calling the LLM. Great for testing and demos.

---

## 🛠️ Configuration

All configuration is done via environment variables in `.env`:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | Yes* | - | Groq API key (recommended) |
| `GOOGLE_API_KEY` | Yes* | - | Google Gemini API key (fallback) |
| `THECATAPI_KEY` | No | - | TheCatAPI key (higher rate limits) |
| `FAKE_LLM_MODE` | No | `false` | Use fake scoring (no API needed) |
| `ROUNDS_PER_GAME` | No | `5` | Number of rounds per game |

*At least one LLM API key required, unless `FAKE_LLM_MODE=true`

---

## 📁 Project Structure

```
Cat-Caption-Cage-Match/
├── main.py              # Main app - Gradio UI + game flow
├── storage.py           # DuckDB database access
├── images.py            # Cat image fetching
├── llm.py               # LLM scoring + roasts (Groq/Gemini)
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
- **LLM:** [Groq](https://groq.com/) (Llama 3.3 70B) or [Google Gemini](https://ai.google.dev/)
- **Images:** [TheCatAPI](https://thecatapi.com) with local fallback
- **Database:** [DuckDB](https://duckdb.org/) (in-memory)

---

## 🐛 Troubleshooting

### "No API key set"
Make sure you've created a `.env` file with your API key and run `source .env` before starting the app.

### "TheCatAPI error"
The game will automatically fall back to a generated placeholder image. This is normal if you don't have a TheCatAPI key or have network issues.

### "LLM scoring failed"
The game automatically falls back to fake scoring. Check your API key is valid.

### Players can't see updates
The Host view auto-refreshes every 2 seconds. Players should click "Refresh Game State" to see updates.

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
