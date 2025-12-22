# BUILD_PROMPT — Cat Caption Cage Match (v2: Web App)

## Product summary

**Cat Caption Cage Match** is a fast, AI-judged party game for remote teams.

- A host creates a session and shares a join code.
- Players join, see the same cat image, and submit one caption (max **15 words**).
- A round continues until all players submit. 
- An LLM scores each caption **0–10** and delivers Gordon Ramsay-style roasts.
- After N rounds (default 3–5), the app declares a winner.

This v2 turns the working demo into a **publicly accessible, always-on** web app with a robust, responsive UI and real multi-user session management.

> Baseline behavior to preserve: join-by-code, 15-word captions, 0–10 scoring + roast tone, multi-round scoreboard.  
> (Aligned to the current repo docs and demo flow.)

---

## Goals

1. **Production-like UX** (mobile-first, responsive, accessible, intuitive).
2. **Real session management** (multiple sessions, multiple rounds, player roster).
3. **Real persistence** (Postgres), with a clean storage interface so we can swap implementations.
4. **Real-time gameplay** via **Socket.IO** (lobby updates, round start, timer sync, results).
5. **Deployable publicly**: Next.js on Vercel; FastAPI on Render or Fly.io.

## Non-goals (for this build)

- Full user accounts / OAuth
- Payments
- Complex moderation pipeline
- Multi-region scaling (we’ll design so it can be added later)
- Timer (may be implemented later)

---

## Architecture (monorepo)

```
/apps
  /web              # Next.js + Tailwind + shadcn/ui
/services
  /api              # FastAPI + Socket.IO + LLM + game orchestration
/packages
  /shared           # Shared types/schemas (optional but recommended)
```

### Frontend (apps/web)

- **Next.js (App Router) + TypeScript**
- **TailwindCSS + shadcn/ui**
- `socket.io-client` for realtime
- Accessibility-first:
  - AA/AAA contrast targets
  - Keyboard navigation and focus states
  - Reduced motion support
  - Clear error states and reconnect behavior

### Backend (services/api)

- **FastAPI**
- **python-socketio** (ASGI) for Socket.IO server
- Postgres (SQLAlchemy 2.x async + asyncpg) + Alembic migrations
- Stateless web servers; state lives in Postgres
- LLM integration (Groq/Gemini). If LLM fails, return graceful fallback scoring.

### Storage interface

Implement a `Storage` abstraction so the game engine doesn’t care if the backing store is Postgres, SQLite, or in-memory.

- `Storage` (interface)
- `PostgresStorage` (production)
- `InMemoryStorage` (tests/dev)

---

## UX flows (must support)

### 1) Landing
- Two primary CTAs: **Host a game** / **Join a game**
- Simple explanation of rules; no clutter

### 2) Host creates session
- Host enters display name
- Session code created and shown prominently with **Copy** button
- Lobby shows player list, connection status, and **Start round** button
- Host selects number of rounds (default 3)

### 3) Players join
- Player enters session code + display name
- Enters lobby view and waits

### 4) Round running
- Everyone receives the same image and authoritative `endsAt` timestamp
- Player can submit once; after submit, input locks with confirmation

### 5) Results
- Reveal all captions + scores + roast per caption
- Show round winner
- Update cumulative leaderboard
- Host can start next round until complete

### 6) Game over
- Winner screen
- “Play again” (new session or reset session)

---

## Reliability, security, and abuse resistance (minimum)

- Keep all **LLM keys** and TheCatAPI key server-side only.
- Basic **rate limiting**:
  - join attempts per IP
  - caption submissions per player per round
- Input validation:
  - displayName length limits
  - caption max 15 words (+ max characters)
- Session expiry:
  - sessions expire after inactivity (e.g., 2 hours)
- Reconnect handling:
  - clients can reconnect and re-sync lobby/round state

---

## Deployment

- **Frontend:** Vercel (Next.js)
- **Backend:** Render or Fly.io (FastAPI + Socket.IO)
- **Database:** Postgres (managed)

### Environment variables

Backend (`services/api/.env`):
- `DATABASE_URL`
- `APP_SECRET` (for signing player tokens)
- `CORS_ORIGINS` (e.g., `https://your-vercel-app.vercel.app`)
- `THECATAPI_KEY` (optional)
- `LLM_PROVIDER` (`groq` | `gemini`)
- Provider keys:
  - `GROQ_API_KEY`
  - `GEMINI_API_KEY`

Frontend (`apps/web/.env.local`):
- `NEXT_PUBLIC_API_BASE_URL` (e.g., `https://api.yourapp.com`)
- `NEXT_PUBLIC_SOCKET_URL` (often same as API base)

---

## Engineering constraints

- Keep it **simple, hackable, and fun**, but **not fragile**.
- Prefer “boring” tech over cleverness.
- Add observability from day one:
  - structured logs in backend
  - simple request IDs
- Write minimal tests where they buy safety:
  - storage methods
  - session lifecycle
  - word-limit enforcement
