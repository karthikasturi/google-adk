# Day 03 Lab Guide
## eComBot v2 — Tool Calling and In-Memory Session State

---

### Starting state
- eComBot v1 is working and testable via ADK Web.
- Repository structure includes at least `src/agents/`, `src/tools/`, `src/config/`, and `tests/`.
- OpenRouter API key is available in `.env`.

### Target state
- eComBot v2 has one callable tool registered with `@tool`.
- `get_order_status(order_id)` is implemented in `src/tools/order_tools.py`.
- In-memory session state stores the customer name and last queried order across turns.
- ADK Web is used only to validate behavior, not as the main runtime flow.
- The lab stays on small, incremental pieces that move the capstone forward.

### Capstone alignment
This session adds the first production-like capability that will later feed into the full eComBot system: a reusable tool layer and short-term session memory. The goal is to build a small, correct piece now so it can later be reused by the Support Agent, Redis-backed state, and external backend integrations.

### Repository layout for this session
```text
ecombot/
├── src/
│   ├── agents/
│   │   └── support_agent.py
│   ├── tools/
│   │   └── order_tools.py
│   └── config/
│       └── settings.py
├── tests/
│   └── test_support_agent_manual.md
├── .env
├── .env.example
└── requirements.txt
```

---

## Task 1 — Create the tool module

**Goal:** Implement `get_order_status` as a mock tool using the `@tool` decorator.

1. Create `src/tools/__init__.py`.
2. Create `src/tools/order_tools.py`.
3. Implement `get_order_status(order_id: str) -> dict` with mock data.
4. Return structured data with at least `order_id`, `status`, `eta`, and `carrier`.
5. Add clean error handling:
   - Invalid format returns `{"error": "Invalid order ID format."}`.
   - Missing order returns `{"error": f"Order {order_id} not found."}`.

**Sample mock data:**
```python
MOCK_ORDERS = {
    "ORD-001": {"order_id": "ORD-001", "status": "Shipped", "eta": "5 Jun 2026", "carrier": "BlueDart"},
    "ORD-002": {"order_id": "ORD-002", "status": "Processing", "eta": "7 Jun 2026", "carrier": "DTDC"},
    "ORD-003": {"order_id": "ORD-003", "status": "Delivered", "eta": "Already delivered", "carrier": "FedEx"},
}
```

**Checkpoint:** Import the module and call `get_order_status("ORD-001")` directly in Python. Confirm it returns a dict.

---

## Task 2 — Wire the tool into the agent

**Goal:** Register the tool in `support_agent.py` so ADK can use it.

1. Open `src/agents/support_agent.py`.
2. Import `get_order_status` from `src.tools.order_tools`.
3. Register it in the agent's tool list.
4. Update the instruction so the agent knows when to use the tool.

**Instruction example:**
```text
When a customer asks about their order, use the get_order_status tool.
Ask for the order ID if it is missing.
Do not guess order details.
Use the tool output directly in the response.
```

**Checkpoint:** Start ADK Web and confirm the agent shows the tool as available.

---

## Task 3 — Validate tool use in ADK Web

**Goal:** Use ADK Web only to confirm the new piece works.

Run these prompts one at a time:

- `Where is my order ORD-001?`
- `Track ORD-002 for me`
- `What is the status of ORD-999?`
- `Track order XYZ-100`

**Expected behavior:**
- Valid IDs call the tool and return structured output.
- Missing orders return a polite not-found response.
- Invalid IDs return a polite format error.
- No invented order details.

**Checkpoint:** ADK Web shows the tool call, tool inputs, and tool outputs clearly.

---

## Task 4 — Add in-memory session state

**Goal:** Store a small amount of context across turns.

1. Confirm `InMemorySessionService` is used in the runner.
2. Store the customer name when the user introduces themselves.
3. Store the last queried order ID after an order lookup.
4. Read the stored name in follow-up replies.

**Example keys:**
```python
tool_context.state["customer_name"] = "Priya"
tool_context.state["last_order_id"] = "ORD-001"
```

**Checkpoint:** The ADK Web state panel shows the stored values after the relevant turns.

---

## Task 5 — Multi-turn validation

**Goal:** Prove the state survives across a small conversation.

Use one ADK Web session and run:

| Turn | Input | Expected |
|------|-------|----------|
| 1 | `Hi, my name is Priya.` | Agent stores the name |
| 2 | `Where is my order ORD-001?` | Agent calls the tool and uses Priya in the reply |
| 3 | `What about ORD-002?` | Agent reuses the stored name |
| 4 | `Can you track ZZ-999?` | Agent handles the invalid format gracefully |

**Checkpoint:** The agent does not ask for the name again after Turn 1.

---

## Task 6 — Document the checks

**Goal:** Capture the work in a manual test file.

Create `tests/test_support_agent_manual.md` and record:
- Input.
- Expected tool call.
- Expected reply behavior.
- Observed result.
- Pass/fail.

**Minimum scenarios:**
- One valid order lookup.
- One not-found order.
- One invalid format.
- One multi-turn sequence.

---

## Stretch goal — Move toward a real data source

**Goal:** Prepare this tool to use a real backend later.

1. Replace the mock order dictionary with a small database or service call.
2. Add a thin data-access layer in `src/services/` or `src/tools/`.
3. Keep the tool interface the same so later modules can reuse it.
4. Optionally run a local Postgres, SQLite, or Redis-backed store and read order data from it.
5. Update the tool so failures from the real data source still return clean error dicts.

**Why this matters:**
This keeps the Day 03 implementation small, but makes it easy to evolve into the later FastMCP-backed and persistent-state versions without rewriting the agent logic.

---

## Verification checklist

- [ ] `get_order_status` exists in `src/tools/order_tools.py`.
- [ ] The tool is registered with the agent.
- [ ] Valid order lookups return structured data.
- [ ] Not-found and invalid format paths return graceful errors.
- [ ] `customer_name` is stored in session state.
- [ ] `last_order_id` is stored in session state.
- [ ] Multi-turn behavior preserves context.
- [ ] ADK Web is used only to validate the working piece.
- [ ] Manual test notes are saved in `tests/test_support_agent_manual.md`.

---

## Next step
Once this small piece works, the next session will harden state management and move toward more durable storage and richer backend integrations.
