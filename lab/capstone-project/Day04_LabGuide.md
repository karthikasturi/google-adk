# Day 04 Lab Guide
## eComBot v2 — Redis Session Persistence and PostgreSQL Tools

---

### Starting state
- eComBot v2 from Day 03 is working and testable via ADK Web.
- The repo already has `src/agents/`, `src/tools/`, `src/config/`, `src/services/`, and `tests/`.
- Day 03 tools still use mock or simple in-memory data.
- OpenRouter API key is available in `.env`.
- Redis and PostgreSQL are not yet wired into the agent runtime.

### Target state
- eComBot v2 uses Redis-backed session persistence for conversation continuity.
- PostgreSQL is used for real tools and durable data storage.
- `get_order_status(order_id)`, `cancel_order(order_id)`, and `lookup_product(product_name)` are backed by PostgreSQL.
- Session history is persisted to PostgreSQL separately from ADK session state.
- The lab validates restart behavior, tool failure handling, and clean config-driven credentials.
- The implementation stays incremental and reusable for later capstone modules.

### Capstone alignment
This session upgrades the agent from tool calling with memory to tool calling with durable state boundaries. The goal is to make the session model clear enough that later modules can reuse the same design for Redis-backed continuity, external tools, observability, and eventual multi-agent routing.

### Repository layout for this session
```text
ecombot/
├── src/
│   ├── agents/
│   │   └── support_agent.py
│   ├── tools/
│   │   ├── order_tools.py
│   │   └── product_tools.py
│   ├── services/
│   │   ├── db.py
│   │   ├── session_service.py
│   │   └── history_service.py
│   └── config/
│       └── settings.py
├── scripts/
│   └── init_db.sql
├── tests/
│   └── test_support_agent_manual.md
├── .env
├── .env.example
├── docker-compose.yml
└── requirements.txt
```

---

## Task 1 — Add the infrastructure

**Goal:** Set up Redis and PostgreSQL for real session persistence and real tool data.

1. Create `docker-compose.yml`.
2. Add Redis with password protection and persistence enabled.
3. Add PostgreSQL with password protection, a mounted volume, and an init SQL script.
4. Add health checks for both services.
5. Create `.env.example` with all required credentials.

**What to include in `.env.example`:**
- Redis host, port, password.
- PostgreSQL host, port, database, user, password.
- OpenRouter and LangSmith keys if already used in the repo.

**Checkpoint:** `docker compose up` starts both services cleanly, and both are reachable from the app.

---

## Task 2 — Seed PostgreSQL

**Goal:** Replace mock data with realistic PostgreSQL seed data.

1. Create `scripts/init_db.sql`.
2. Add `orders`, `products`, and `session_history` tables.
3. Insert at least 5 rows into `orders` and `products`.
4. Include a few edge cases:
   - cancelled order,
   - out-of-stock product,
   - invalid or inactive product row if useful for tests.

**Suggested demo IDs:**
- `ORD-001`, `ORD-002`, `ORD-003`
- `PRD-101`, `PRD-102`, `PRD-103`

**Checkpoint:** Tables are created automatically and seed data is visible in PostgreSQL.

---

## Task 3 — Add config handling

**Goal:** Move all secrets and service endpoints into config.

1. Create or update `src/config/settings.py`.
2. Read values from environment variables only.
3. Add helpers for Redis URL and PostgreSQL DSN.
4. Avoid hardcoded passwords, URLs, or tokens.

**Checkpoint:** The application starts using `.env` values, not inline secrets.

---

## Task 4 — Add PostgreSQL access

**Goal:** Build a reusable database connection layer.

1. Create `src/services/db.py`.
2. Add a PostgreSQL connection pool.
3. Make the connection layer reusable from tools and history services.
4. Add clean error handling for database failures.

**Stretch goal:** Add a small repository helper layer so SQL stays out of the agent code.

**Checkpoint:** A simple query against `orders` or `products` returns expected data.

---

## Task 5 — Add Redis session persistence

**Goal:** Make session continuity survive process restart.

1. Create `src/services/session_service.py`.
2. Wire Redis into the ADK session service.
3. Store working context in session state:
   - `current_order_id`
   - `current_customer_name`
   - `current_product_id`
   - `last_intent`
   - `last_lookup_key`

**Important:** Redis is for short-lived working memory and session continuity, not for durable business history.

**Stretch goal:** Restart the app and verify the session context is restored correctly.

**Checkpoint:** A follow-up question does not require the user to repeat the previous order or product ID.

---

## Task 6 — Persist session history

**Goal:** Store conversation history in PostgreSQL.

1. Create `src/services/history_service.py`.
2. Save each turn with:
   - `session_id`
   - `user_id`
   - `role`
   - `content`
   - `tool_calls`
   - timestamp
3. Add a read method to retrieve the conversation by session ID.

**Stretch goal:** Add a simple admin/debug script to print session history for a given session.

**Checkpoint:** The full conversation can be replayed from PostgreSQL after the session ends.

---

## Task 7 — Replace mock tools

**Goal:** Implement real tools backed by PostgreSQL.

1. Update `src/tools/order_tools.py`.
2. Add `src/tools/product_tools.py`.
3. Implement:
   - `get_order_status(order_id)`
   - `cancel_order(order_id)`
   - `lookup_product(product_name)`

**Tool rules:**
- Validate input before querying.
- Return structured outputs.
- Handle not found and invalid format cases cleanly.
- Catch database exceptions and return safe error messages.
- Update session state when useful.

**Expected session behavior:**
- Store the last order ID after lookup.
- Store the last product queried.
- Reuse the stored values in follow-up turns.

**Checkpoint:** The agent queries PostgreSQL rather than a mock dictionary.

---

## Task 8 — Wire the agent

**Goal:** Update the Day 03 agent to use the new persistence and tools.

1. Update `src/agents/support_agent.py`.
2. Register the PostgreSQL-backed tools.
3. Keep the instruction clear about when to use a tool versus session state.
4. Make sure the agent does not invent order or product details.

**Suggested instruction focus:**
- Ask for missing order/product IDs.
- Use the tool when lookup is needed.
- Reuse session state for short follow-ups.
- Never guess details not returned by the tool.

**Checkpoint:** The agent responds correctly across a multi-turn conversation with continuity.

---

## Task 9 — Validate the core flow

**Goal:** Prove the end-to-end behavior works.

Run one ADK Web session and test:

| Turn | Input | Expected |
|------|-------|----------|
| 1 | `Hi, my name is Priya.` | Name stored in session state |
| 2 | `Where is my order ORD-001?` | Tool call and structured output |
| 3 | `What about that same order?` | Session state reused |
| 4 | `Show me PRD-101` | Product lookup via PostgreSQL |
| 5 | `What is the price again?` | Last product reused |
| 6 | Restart the app and ask a follow-up | Session continuity restored |

**Stretch goal:** Add a manual test file with observed results and pass/fail notes.

**Checkpoint:** The agent keeps context across turns and after restart.

---

## Task 10 — Validate failure cases

**Goal:** Test production-style error handling.

### Required failures
- Invalid order ID.
- Order already cancelled.
- Missing product name.
- PostgreSQL unavailable.
- Redis unavailable.
- Empty tool input.

### Expected behavior
- Return safe error messages.
- Do not leak stack traces.
- Do not fabricate tool results.
- Ask for clarification when needed.

### Stretch goal
Add one failure test for a malformed row or a missing table to verify database robustness.

**Checkpoint:** Each failure path is handled cleanly and predictably.

---

## Task 11 — Production-readiness checks

**Goal:** Make the implementation look and behave like a real system.

Verify the following:

- All secrets are externalized.
- Redis is password protected.
- PostgreSQL is password protected.
- Health checks are present.
- Session state is not used as permanent storage.
- PostgreSQL is not used as transient scratchpad memory.
- History is durable and queryable.
- Tools validate inputs before execution.
- Errors are user-safe.

**Stretch goal:** Add structured logging around DB calls and session updates.

**Checkpoint:** The implementation is ready to grow into later ADK modules.

---

## Verification checklist
- [ ] `docker-compose.yml` starts Redis and PostgreSQL.
- [ ] `scripts/init_db.sql` creates and seeds the tables.
- [ ] `settings.py` reads all config from environment variables.
- [ ] `db.py` provides reusable PostgreSQL access.
- [ ] `session_service.py` enables Redis-backed session continuity.
- [ ] `history_service.py` stores durable conversation history.
- [ ] PostgreSQL-backed tools return structured results.
- [ ] Session state persists across turns and after restart.
- [ ] Failure scenarios return safe messages.
- [ ] Manual test notes are saved in `tests/test_support_agent_manual.md`.

---

## Stretch goal — Move toward the capstone

**Goal:** Make this work directly reusable for later eComBot modules.

1. Keep the tool interfaces stable so they can later plug into FastMCP or service wrappers.
2. Keep the session-state keys clean so multi-agent routing can build on them later.
3. Keep the history service separate so observability and evaluation can consume it later.
4. Keep the DB access reusable so future RAG, tool, or admin workflows can share the same foundation.

**Why this matters:**  
This lab should not feel like a one-off demo. It should feel like the first durable foundation for the final eComBot system.

---

## Next step
Once this lab works, the next session will take the same eComBot foundation and move it toward retrieval, grounding, and stronger production behavior.
