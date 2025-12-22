# API_CONTRACT — Cat Caption Cage Match (FastAPI + Socket.IO)

This contract defines:
1) REST routes (for initial actions, admin/host actions, fetches)
2) Socket.IO events (for realtime gameplay)

The REST layer is intentionally small; realtime events carry most gameplay state.

---

## Conventions

### IDs and codes
- `sessionCode`: 6 uppercase alphanumerics (e.g., `K9Q2TZ`)
- `sessionId`, `playerId`, `roundId`: ULID/UUID strings

### Auth model (lightweight)
- No accounts.
- On join, server issues:
  - `playerId`
  - `playerToken` (signed; stored client-side)
- Clients send `playerToken` for privileged actions (submit caption, host actions).

### Time authority
- Server provides `serverTime` and authoritative `endsAt`.
- Clients render timers based on server timestamps (not local “start now”).

### Word limit
- Caption: max 15 words
- Server enforces; frontend also validates.

---

## Data models (shape)

### Session
```json
{
  "sessionId": "01J...",
  "sessionCode": "K9Q2TZ",
  "status": "lobby|in_round|revealing|finished|expired",
  "hostPlayerId": "01J...",
  "settings": { "roundsTotal": 3, "roundSeconds": 45 },
  "createdAt": "2025-12-22T12:00:00Z",
  "expiresAt": "2025-12-22T14:00:00Z"
}
```

### Player
```json
{
  "playerId": "01J...",
  "displayName": "Erinn",
  "isHost": false,
  "joinedAt": "2025-12-22T12:01:00Z"
}
```

### Round
```json
{
  "roundId": "01J...",
  "number": 1,
  "imageUrl": "https://...",
  "status": "active|scoring|revealed",
  "startsAt": "2025-12-22T12:05:00Z",
  "endsAt": "2025-12-22T12:05:45Z"
}
```

### Caption + Score
```json
{
  "captionId": "01J...",
  "playerId": "01J...",
  "text": "When you realize it's Monday again",
  "submittedAt": "2025-12-22T12:05:20Z",
  "score": {
    "humour": 8,
    "relevance": 7,
    "total": 15,
    "roast": "Brave attempt. Still tastes like microwave lasagna."
  }
}
```

---

## REST API

Base URL: `/api`

### Health
- `GET /api/health`
  - 200 `{ "status": "ok" }`

### Sessions

#### Create session (Host)
- `POST /api/sessions`
Request:
```json
{ "hostDisplayName": "Erinn", "settings": { "roundsTotal": 3, "roundSeconds": 45 } }
```
Response 201:
```json
{
  "session": { "...": "..." },
  "host": { "playerId": "01J...", "playerToken": "..." }
}
```

#### Get session state
- `GET /api/sessions/{sessionCode}`
Response 200:
```json
{
  "session": { "...": "..." },
  "players": [ { "...": "..." } ],
  "currentRound": { "...": "..." } | null,
  "leaderboard": [ { "playerId": "...", "displayName": "...", "totalScore": 42 } ]
}
```

#### Join session (Player)
- `POST /api/sessions/{sessionCode}/players`
Request:
```json
{ "displayName": "Sam" }
```
Response 201:
```json
{ "playerId": "01J...", "playerToken": "..." }
```

#### End session (Host)
- `POST /api/sessions/{sessionCode}/end`
Headers: `Authorization: Bearer <playerToken>`
Response 200: `{ "ok": true }`

### Rounds

#### Start round (Host)
- `POST /api/sessions/{sessionCode}/rounds`
Headers: `Authorization: Bearer <playerToken>`
Request (optional overrides):
```json
{ "roundSeconds": 45 }
```
Response 201:
```json
{ "round": { "...": "..." } }
```

#### Reveal results (Host)
- `POST /api/sessions/{sessionCode}/rounds/{roundId}/reveal`
Headers: `Authorization: Bearer <playerToken>`
Response 200:
```json
{ "round": { "...": "..." }, "captions": [ { "...": "..." } ], "leaderboard": [ ... ] }
```

### Captions

#### Submit caption (Player)
- `POST /api/sessions/{sessionCode}/rounds/{roundId}/captions`
Headers: `Authorization: Bearer <playerToken>`
Request:
```json
{ "text": "15 words max..." }
```
Response 201:
```json
{ "captionId": "01J...", "locked": true }
```

---

## Socket.IO realtime contract

### Connection
- Namespace: `/ws`
- Client connects with:
  - `auth: { sessionCode, playerToken }` (or joins later via event)

### Rooms
- Each session has a room: `session:{sessionCode}`
- Each round can have a room: `round:{roundId}` (optional)

### Client → Server events

#### `session:join`
Payload:
```json
{ "sessionCode": "K9Q2TZ" }
```
Ack:
```json
{ "ok": true, "state": { "session": {...}, "players": [...], "currentRound": {...}|null, "leaderboard":[...] } }
```

#### `host:start_round`
Payload:
```json
{ "sessionCode": "K9Q2TZ" }
```
Ack:
```json
{ "ok": true, "round": { "...": "..." } }
```

#### `player:submit_caption`
Payload:
```json
{ "sessionCode": "K9Q2TZ", "roundId": "01J...", "text": "..." }
```
Ack:
```json
{ "ok": true, "locked": true }
```

#### `host:reveal_round`
Payload:
```json
{ "sessionCode": "K9Q2TZ", "roundId": "01J..." }
```
Ack:
```json
{ "ok": true }
```

#### `ping`
Payload: `{ "t": 123 }`
Ack: `{ "t": 123, "serverTime": "2025-12-22T12:00:00Z" }`

---

### Server → Client events

#### `session:state`
Emitted whenever session state changes (player joins/leaves, status changes).
Payload:
```json
{ "session": {...}, "players": [...], "currentRound": {...}|null, "leaderboard":[...] }
```

#### `round:started`
Payload:
```json
{ "round": { "roundId":"...", "number":1, "imageUrl":"...", "startsAt":"...", "endsAt":"..." } }
```

#### `round:tick` (optional)
If you want server-driven ticks (usually not necessary):
```json
{ "roundId":"...", "serverTime":"...", "secondsRemaining": 12 }
```

#### `caption:locked`
Broadcast when a player submits (optionally anonymized):
```json
{ "roundId":"...", "playerId":"01J...", "submitted": true }
```

#### `round:revealed`
Payload:
```json
{ "round": {...}, "captions": [ {...} ], "leaderboard":[...] }
```

#### `error`
Payload:
```json
{ "code": "NOT_FOUND|UNAUTHORIZED|VALIDATION|RATE_LIMIT", "message": "..." }
```

---

## Scaling notes (important for Socket.IO)

- With **1 backend instance**, Socket.IO “just works”.
- With **multiple instances**, you need:
  - sticky sessions at the load balancer **or**
  - a Socket.IO adapter (typically Redis) so events broadcast across instances.

Start single-instance. Add Redis adapter only when needed.
