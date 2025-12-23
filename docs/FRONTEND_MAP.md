# FRONTEND_MAP — Next.js page map + component list

This is the minimal UI map aligned to the current game flow: host creates session → lobby → rounds → reveal → leaderboard → end.

---

## Page map (Next.js App Router)

### Public
- `/` — Landing
  - Buttons: “Host a game” / “Join a game”
  - Short rules summary

### Host flow
- `/host` — Create session
  - Host name input
  - Settings: roundsTotal (3–5)
  - CTA: Create session
  - Redirect to `/s/[code]/host`

- `/s/[code]/host` — Host lobby + host controls
  - Session code (copy)
  - Player list (live)
  - Start round button
  - During a round: host sees the same round screen + “Reveal results” button (or auto reveal)

### Player flow
- `/join` — Join session
  - Session code + display name
  - Redirect to `/s/[code]/play`

- `/s/[code]/play` — Player lobby + game screens
  - Lobby view until round starts
  - Round view: image + caption input
  - Results view: scores + roast + leaderboard

### Optional
- `/s/[code]/results` — Final results summary (shareable)

---

## Top-level layout components

- `<AppShell />`
  - Header: logo + title
  - Right side: connection indicator + accessibility toggle
  - Main: page content
- `<AccessibilityMenu />`
  - Font size (base/large/x-large)
  - Theme (high-contrast / soft)
  - Reduced motion toggle

---

## Core UI components

### Session + lobby
- `<SessionCodeBadge code="K9Q2TZ" />` (copy to clipboard)
- `<PlayerList players=[...] />`
- `<ConnectionStatus state="connected|reconnecting|offline" />`
- `<HostControls />`
  - Start round
  - Reveal results
  - End session

### Round
- `<CatImage src="..." />` (responsive, max height, alt text)
- `<RoundTimer endsAt="..." serverTime="..." />`
- `<CaptionComposer maxWords={15} />`
  - word counter
  - submit button
  - validation messages
- `<SubmissionStatus locked />`

### Results + leaderboard
- `<ResultsGrid captions=[...] />`
  - `<CaptionCard />` per player:
    - name
    - caption text
    - score
    - roast
- `<RoundWinnerBanner />`
- `<LeaderboardTable rows=[...] />`
- `<PlayAgainCTA />`

### Feedback + resilience
- `<ToastCenter />` (errors, confirmations)
- `<EmptyState />` (no players, session expired, etc.)
- `<ReconnectBanner />` (attempting reconnect; “refresh” fallback)

---

## State + networking

### Recommended state shape
- `session`: session metadata + settings + status
- `me`: playerId + token + displayName + isHost
- `players`: roster
- `round`: currentRound (imageUrl, endsAt, status)
- `captions`: revealed results (after reveal)
- `leaderboard`: totals

### Client networking
Use REST for:
- create session
- join session
- fetch full state on load/reconnect

Use Socket.IO for:
- live player roster updates
- round started
- caption locked broadcasts
- round revealed + leaderboard updates

### Hooks (suggested)
- `useApi()` — typed REST client
- `useSocket(sessionCode, playerToken)` — connect + join room
- `useSessionState()` — merges REST snapshot + socket deltas
- `useServerTimer(endsAt, serverTime)` — drift-safe timer

---

## UX rules (keep it simple)

- Always show session code and player name at top.
- Never hide the primary next action:
  - lobby → “Waiting for host…”
  - round → “Submit”
  - results → “Waiting for next round…” or “Play again”
- Large tap targets on mobile.
- No distracting animations; respect reduced motion.
- No emojis
