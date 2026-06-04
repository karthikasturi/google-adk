# TravelBot — Evolving Agent Demo

**Google ADK · LiteLLM · OpenRouter · Session Persistence (v3)**

A progressive demo showing an AI agent evolve across three versions: from a basic chatbot to tool-calling to production persistence.

---

## Versions

| Version | Features | Session Storage | Data Source |
|---------|----------|---|---|
| **v1** | Basic agent, system prompt only | None | N/A |
| **v2** | Tool calling (flights, hotels) | In-memory | Static Python dicts |
| **v3** | Database tools, persistent sessions | PostgreSQL / Redis | PostgreSQL tables |

---

## Quick start

### V1–V2 (no infrastructure needed)

```bash
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY

python demo.py v1
# or: python demo.py v2
```

### V3 (requires Docker infrastructure)

```bash
# Terminal 1: Start services
docker compose -f ../day04/docker-compose.yml up -d postgres redis

# Terminal 2: Run the demo
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY + database credentials

python demo.py v3
```

---

## V3 session backends

Control where session state is stored:

```bash
# PostgreSQL (default — full durability)
SESSION_BACKEND=database python demo.py v3

# Redis only (fast, no SQL)
SESSION_BACKEND=redis python demo.py v3

# In-memory (no persistence, tests only)
SESSION_BACKEND=memory python demo.py v3
```

---

## Docker infrastructure (for v3)

The demo uses the same Docker Compose setup as `lab/demo/day04/`:

```bash
cd ../day04

# Start both PostgreSQL and Redis
docker compose up -d

# Check health
docker compose ps

# Stop (data preserved)
docker compose down

# Full reset (delete all data)
docker compose down -v
```

---

## V3-specific features

### Booking lookups

```
"Check booking TB-1001 for me."
↓ → get_booking_status() queries PostgreSQL bookings table
↓ → current_booking_id saved to session state
```

### Follow-ups without repeating IDs

```
"What's the passenger name?"
↓ → Aria refers to session state, no lookup needed
```

### Flight search with database

```
"Find flights from Mumbai to London."
↓ → search_flights() queries PostgreSQL flights table
↓ → results include price, duration, available seats
```

### Cancellations with state

```
"Cancel my booking."
↓ → Agent uses current_booking_id from session
↓ → cancel_booking() updates status to Cancelled
```

### Durable conversation history

Every turn is recorded to PostgreSQL `session_history` table:
- `role` (user / model)
- `content` (the text)
- `tool_calls` (JSON of tool calls made)
- `created_at` (timestamp)

### Session persistence

Sessions survive process restarts:

```bash
python demo.py v3
# → Interactive REPL, session_id shown
# → ctrl-C

python demo.py v3
# → New process, can reconnect to same session_id
# → State loaded from PostgreSQL
```

---

## File structure

```
travelbot/
├── config.py           # Settings from env vars
├── db.py               # psycopg2 connection pool (v3)
├── redis_client.py     # Redis helpers for state snapshots (v3)
├── history.py          # Durable history writer (v3)
├── demo.py             # Main REPL (v1, v2, v3 menu)
├── requirements.txt    # Dependencies
├── .env.example        # Environment template
├── shared/
│   ├── session.py      # Session factory (supports 3 backends)
│   ├── tools.py        # All tools (v2 static + v3 DB-backed)
│   ├── models.py       # build_agent() helper
│   └── __init__.py
├── v1/
│   ├── agent.py        # Basic agent (no tools)
│   └── __init__.py
├── v2/
│   ├── agent.py        # Tools + in-memory session
│   └── __init__.py
└── v3/
    ├── agent.py        # Tools + persistent session
    └── __init__.py
```

---

## V3 tools

All v3 tools also include the v2 tools (backward compatible).

### New in v3

#### `get_booking_status(booking_id)` — Query PostgreSQL `bookings` table

Saves `current_booking_id` and `current_passenger` to session state.

```
→ "Check booking TB-1001 for me."
← Booking details: passenger, flight, route, departure, status
```

#### `cancel_booking(booking_id)` — Update booking status

Accepts `booking_id="current"` to use session context. Rejects already-cancelled bookings.

```
→ "Cancel booking TB-1002."
← Success: booking marked Cancelled

→ "Cancel TB-1003."
← Error: already cancelled (graceful)
```

#### `search_flights(origin, destination)` — Query PostgreSQL `flights` table

Saves `last_search_origin` and `last_search_destination` to session state.

```
→ "Find flights from Mumbai to London."
← List of flights with price, duration, seats, class
```

### From v2 (retained)

- `get_flight_status(flight_number)` — Static mock data
- `search_hotels(city)` — Static mock data
- `save_traveler_name(name)` — Saves to session state
- `get_trip_summary()` — Reads all session context

---

## Trying the demo

### Interactive menu mode

```bash
python demo.py
# Menu appears; choose v1, v2, or v3
```

### Direct version

```bash
python demo.py v1    # Skip to v1
python demo.py v2    # Skip to v2
python demo.py v3    # Skip to v3 (requires Docker)
```

### V3 with different session backends

```bash
SESSION_BACKEND=memory python demo.py v3
SESSION_BACKEND=redis python demo.py v3
SESSION_BACKEND=database python demo.py v3
```

---

## Comparing versions

Run them in sequence to see the evolution:

```bash
python demo.py
# → Choose v1
# → Test: "Can you book me a flight?" (no tools, Aria declines)
# → Finish with 'q'
# → Offered: "Continue to v2?" → Say yes
# → Test: "I'm flying on AI-204. What's the status?" (tool call!)
# → Test: "My name is Priya. Find a hotel in Tokyo." (state context)
# → Finish
# → Offered: "Continue to v3?" → Say yes
# → Test: "Check booking TB-1001." (database lookup!)
# → Test: "What's the passenger?" (no booking ID needed — state!)
```

---

## Setting up Docker infrastructure

If you haven't already:

```bash
cd ../day04

# Copy .env template
cp .env.example .env

# Edit .env if needed (defaults usually work)

# Start services
docker compose up -d

# Check they're healthy
docker compose ps

# View logs
docker compose logs -f postgres
docker compose logs -f redis
```

The same Docker setup serves both `lab/demo/day04/` and `lab/travelbot/v3`.

---

## Known limitations

- V3 requires PostgreSQL and optionally Redis to be running
- Session history is only recorded if the database is available
- If Redis is down, state snapshots are skipped but sessions still work via PostgreSQL
- In-memory sessions (v1–v2) are lost when the process exits
