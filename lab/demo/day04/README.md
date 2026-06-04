# Day 04 — PostgreSQL Tools + Redis Session Persistence

**Google ADK · LiteLLM · OpenRouter · PostgreSQL · Redis**

Upgrades Day 03 from mock in-memory data to production-style persistence:
real database-backed tools, session state that survives process restarts,
and durable conversation history.

---

## What's new in Day 04

| Capability | Day 03 | Day 04 |
|---|---|---|
| Tool data source | Static dicts in Python | PostgreSQL tables |
| Session storage | In-memory (lost on restart) | PostgreSQL or Redis |
| Conversation history | None | `session_history` table in PostgreSQL |
| State cache | None | Redis (fast working-memory snapshot) |
| Booking tools | `get_flight_status`, `search_hotels` | `get_booking_status`, `cancel_booking`, `search_flights` |

---

## Prerequisites

- Docker + Docker Compose
- Python 3.12+
- An [OpenRouter](https://openrouter.ai/keys) API key

---

## Setup (run once, in order)

### 1 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2 — Configure environment

```bash
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY
```

### 3 — Start infrastructure

```bash
docker compose up -d
```

Wait for both services to be healthy:

```bash
docker compose ps
```

You should see `healthy` for both `travelbot-postgres` and `travelbot-redis`.

### 4 — Run the demo

```bash
python demo.py
```

Skip scripted scenarios and go straight to the REPL:

```bash
python demo.py --repl
```

---

## Scenario walkthrough

The demo runs six scripted scenarios automatically, then offers a free REPL.

| # | Scenario | What it demonstrates |
|---|---|---|
| 1 | `"Check booking TB-1001"` | `get_booking_status` queries PostgreSQL |
| 2 | `"What's the departure date?"` | Follow-up uses session state — no booking ID repeated |
| 3 | `"Flights from Mumbai to London"` | `search_flights` queries the flights table |
| 4 | `"Cancel booking TB-1002"` | `cancel_booking` updates the row to Cancelled |
| 5 | `"Cancel TB-1003"` | Graceful error — booking is already Cancelled |
| 6 | *(automatic)* | Runner is recreated with the same session_id; state recovered from PostgreSQL |
| + | *(automatic)* | Full conversation history printed from `session_history` table |

---

## Session backends

Control which session service ADK uses via the `SESSION_BACKEND` env var.

### PostgreSQL (default — full persistence)

```bash
python demo.py
# or explicitly:
SESSION_BACKEND=database python demo.py
```

Sessions are stored in PostgreSQL via `DatabaseSessionService`.  
State survives process restarts. Requires `docker compose up -d postgres`.

### Redis only (no SQL needed)

```bash
SESSION_BACKEND=redis python demo.py
```

Sessions are stored in Redis via `RedisSessionService`.  
Fast, survives restarts as long as Redis is running.  
Requires `docker compose up -d redis`.

### In-memory (no infrastructure — tests only)

```bash
SESSION_BACKEND=memory python demo.py
```

Uses `InMemorySessionService`. State is lost when the process exits.  
Useful for running unit tests without any running services.

---

## Docker Compose commands

```bash
# Start both services
docker compose up -d

# Start only one service
docker compose up -d postgres
docker compose up -d redis

# Check service health
docker compose ps

# View logs
docker compose logs -f postgres
docker compose logs -f redis

# Stop services (data is preserved in volumes)
docker compose down

# Stop and delete all data (full reset)
docker compose down -v
```

---

## Running unit tests

Tests are fully mock-based — no running services required.

```bash
python -m pytest tests/ -v
```

---

## File structure

```
day04/
├── docker-compose.yml      # Redis + PostgreSQL services
├── .env.example            # Environment variable template
├── requirements.txt        # Python dependencies
├── scripts/
│   └── init_db.sql         # Schema + seed data (runs on first Postgres start)
├── config.py               # Settings dataclass — all credentials from env
├── db.py                   # psycopg2 connection pool (sync, for tools)
├── redis_client.py         # Redis helpers — state snapshots + session refs
├── history.py              # Durable conversation history (PostgreSQL)
├── session.py              # Session backend selector (single swap point)
├── tools.py                # DB-backed tool functions
├── agent.py                # Aria — Day 04 LlmAgent
├── demo.py                 # Scripted scenarios + free REPL
└── tests/
    └── test_tools.py       # Unit tests for all tool functions
```

---

## Key design boundaries

| Layer | Storage | Lifetime |
|---|---|---|
| Working memory (`tool_context.state`) | ADK session (PostgreSQL or Redis) | Until session expires |
| State cache | Redis | TTL-controlled (default 1 hour) |
| Conversation history | PostgreSQL `session_history` | Permanent |

Session state is short-lived working memory (current booking, passenger name,
last flight search). Conversation history is an append-only audit trail stored
separately in PostgreSQL — the two are never conflated.
