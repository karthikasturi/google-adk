# TravelBot — Evolving Agent Demo

**Google ADK · LiteLLM · OpenRouter · Session Persistence (v3) · RAG (v4)**

A progressive demo showing an AI agent evolve across four versions: from a basic chatbot to tool-calling to production persistence to retrieval-augmented generation.

---

## Versions

| Version | Features | Session Storage | Data Source |
|---------|----------|---|---|
| **v1** | Basic agent, system prompt only | None | N/A |
| **v2** | Tool calling (flights, hotels) | In-memory | Static Python dicts |
| **v3** | Database tools, persistent sessions | PostgreSQL / Redis | PostgreSQL tables |
| **v4** | Everything in v3 + RAG knowledge base (destination/visa/baggage) | PostgreSQL / Redis | PostgreSQL tables + local ChromaDB |

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

### V4 (v3 infrastructure + a one-time local index)

```bash
# Same Docker services as v3 (see above), plus index the RAG knowledge base
# once — it lives in a local ChromaDB collection, no extra services needed:
python -m rag.embed_catalog

python demo.py v4
```

---

## V3/V4 session backends

Control where session state is stored:

```bash
# PostgreSQL (default — full durability)
SESSION_BACKEND=database python demo.py v4

# Redis only (fast, no SQL)
SESSION_BACKEND=redis python demo.py v4

# In-memory (no persistence, tests only)
SESSION_BACKEND=memory python demo.py v4
```

---

## Docker infrastructure (for v3/v4)

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

## V4-specific features — RAG knowledge base

v4 adds exactly one thing on top of v3: a local knowledge base of destination
guides, visa FAQs, and baggage policies that grounds Aria's answers to
questions her database tools can't handle. Index it once before running v4:

```bash
python -m rag.embed_catalog
```

### How it's wired in

`v4/agent.py` replaces v3's static instruction string with a dynamic
`InstructionProvider` (`_build_instruction`). On every turn it:

1. Reads the user's latest message from `ReadonlyContext.user_content`.
2. Calls `rag.retriever.retrieve()` to fetch the closest-matching chunks
   from the local ChromaDB `travel_kb` collection (embedded via OpenRouter).
3. Appends those chunks — plus grounding/fallback rules — to the base
   instruction, so the model answers from real retrieved text.

Everything else — tools, session backends, history — is untouched from v3.

### Grounded answers

```
"What's the baggage allowance for an economy ticket?"
↓ → retrieve() finds the matching baggage-policy chunk
↓ → Aria answers from that text, not from memory

"Do I need a visa to visit Dubai as an Indian passport holder?"
↓ → retrieve() finds the matching visa-FAQ chunk
↓ → Aria answers from that text, not from memory
```

### Honest fallback

```
"What's the weather like in Reykjavik in October?"
↓ → retrieve() finds nothing relevant
↓ → Aria says plainly that she doesn't have grounded information on
    this, instead of guessing or inventing an answer
```

### Smoke-testing retrieval directly

```bash
python scripts/test_rag.py
```

Runs four queries — a good match, a partial match, a fallback, and a
"hallucination trap" (a question about a fictional TravelBot policy) —
showing both the raw retrieved chunks and Aria's grounded replies.

---

## File structure

```
travelbot/
├── config.py           # Settings from env vars
├── settings.py         # Settings dataclass incl. RAG config (v4)
├── db.py               # psycopg2 connection pool (v3)
├── redis_client.py     # Redis helpers for state snapshots (v3)
├── history.py          # Durable history writer (v3)
├── demo.py             # Main REPL (v1, v2, v3, v4 menu)
├── requirements.txt    # Dependencies
├── .env.example        # Environment template
├── shared/
│   ├── session.py      # Session factory (supports 3 backends)
│   ├── tools.py        # All tools (v2 static + v3 DB-backed)
│   ├── models.py       # build_agent() helper
│   └── __init__.py
├── rag/                # Local RAG knowledge base (v4)
│   ├── embed_catalog.py  # Seed documents + one-time ChromaDB indexing
│   ├── retriever.py      # retrieve(query) used by v4.agent at answer time
│   └── __init__.py
├── scripts/
│   └── test_rag.py     # Smoke test: retrieval + grounded generation (v4)
├── v1/
│   ├── agent.py        # Basic agent (no tools)
│   └── __init__.py
├── v2/
│   ├── agent.py        # Tools + in-memory session
│   └── __init__.py
├── v3/
│   ├── agent.py        # Tools + persistent session
│   └── __init__.py
└── v4/
    ├── agent.py        # v3 + RAG-grounded dynamic instruction
    └── __init__.py
```

---

## V3 tools

All v3 tools also include the v2 tools (backward compatible). v4 reuses the
exact same tool set — its only addition is the RAG knowledge base described
above.

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
# Menu appears; choose v1, v2, v3, or v4
```

### Direct version

```bash
python demo.py v1    # Skip to v1
python demo.py v2    # Skip to v2
python demo.py v3    # Skip to v3 (requires Docker)
python demo.py v4    # Skip to v4 (requires Docker + python -m rag.embed_catalog)
```

### V3/V4 with different session backends

```bash
SESSION_BACKEND=memory python demo.py v4
SESSION_BACKEND=redis python demo.py v4
SESSION_BACKEND=database python demo.py v4
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
# → Finish
# → Offered: "Continue to v4?" → Say yes
# → Test: "What's the baggage allowance for an economy ticket?" (RAG-grounded!)
# → Test: "What's the weather like in Reykjavik in October?" (honest fallback)
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

The same Docker setup serves `lab/demo/day04/`, `lab/travelbot/v3`, and `lab/travelbot/v4`.

---

## Known limitations

- V3/V4 require PostgreSQL and optionally Redis to be running
- Session history is only recorded if the database is available
- If Redis is down, state snapshots are skipped but sessions still work via PostgreSQL
- In-memory sessions (v1–v2) are lost when the process exits
- V4's knowledge base must be indexed once before first use: `python -m rag.embed_catalog`
  (if the `travel_kb` collection is empty, retrieval returns no results and Aria
  falls back to "I don't have grounded information on that")
