# Cat Caption Cage Match - API Backend

FastAPI + Socket.IO backend for the Cat Caption Cage Match game.

## Quick Start

### 1. Create virtual environment

```bash
cd services/api
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Create a `.env` file with your settings:

```bash
# Required
APP_SECRET=your-secret-key-here

# LLM Provider: "groq" | "gemini" | "fake"
LLM_PROVIDER=fake

# Optional API keys
GROQ_API_KEY=your-groq-key
GEMINI_API_KEY=your-gemini-key
THECATAPI_KEY=your-cat-api-key

# CORS (for frontend)
CORS_ORIGINS=["http://localhost:3000"]
```

### 4. Run the server

```bash
python run.py
```

Or with uvicorn directly:

```bash
uvicorn app.main:combined_app --reload --port 8000
```

## API Endpoints

### Health
- `GET /api/health` - Health check

### Sessions
- `POST /api/sessions` - Create a new session
- `GET /api/sessions/{code}` - Get session state
- `POST /api/sessions/{code}/end` - End session (host only)

### Players
- `POST /api/sessions/{code}/players` - Join a session

### Rounds
- `POST /api/sessions/{code}/rounds` - Start a round (host only)
- `POST /api/sessions/{code}/rounds/{roundId}/reveal` - Reveal results (host only)

### Captions
- `POST /api/sessions/{code}/rounds/{roundId}/captions` - Submit caption

## Socket.IO Events

Connect to `/` with Socket.IO client.

### Client → Server
- `session:join` - Join a session room
- `ping` - Time sync

### Server → Client
- `session:state` - Full session state update
- `round:started` - New round started
- `caption:locked` - Player submitted
- `round:revealed` - Round results

## Architecture

```
app/
├── main.py           # FastAPI app + Socket.IO mount
├── config.py         # Settings from environment
├── models.py         # Pydantic schemas
├── dependencies.py   # Dependency injection
├── socket_manager.py # Socket.IO server
├── routers/
│   ├── health.py     # Health endpoint
│   └── sessions.py   # Game endpoints
├── services/
│   ├── tokens.py     # Player token signing
│   ├── images.py     # Cat image fetching
│   └── llm.py        # LLM scoring
└── storage/
    ├── base.py       # Abstract storage interface
    └── memory.py     # In-memory implementation
```

## Development

### Running tests

```bash
pytest
```

### Linting

```bash
ruff check .
ruff format .
```

