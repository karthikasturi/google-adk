# Day 08 Lab Guide – FastMCP and External Integrations (eComBot v5)

## 1. Lab overview

In this lab, you connect **eComBot** to external services through FastMCP, modeling realistic backend integrations for **orders** and **inventory**.
You will build at least one mock MCP server using FastMCP, expose a few order and inventory tools, and wire eComBot so it can call those tools, handle errors, and keep user messaging robust.

## 2. Starting state – what you should already have

Before you start, confirm that your environment matches this starting state:

- A working **eComBot v4** from the previous LiteLLM session, already calling models through a gateway.  
- Repository structure similar to earlier days, for example:  
  - `src/agents/` – eComBot agent definitions (support/sales logic as it exists today).  
  - `src/tools/` – any existing in‑process tools.  
  - `src/services/` – reserved for external services and MCP servers.  
  - `src/config/` – configuration helpers and environment loading.  
  - `tests/` – basic tests or scripts to exercise eComBot flows.  
- FastMCP installed and importable in your Python environment.  
- Docker or a similar runtime available if you plan to run MCP servers as separate processes or containers.

If any of these pieces are missing, align your environment before continuing.

## 3. Target state – what you will build

By the end of this lab, you should have:

- At least one **FastMCP server** running under `src/services/`, exposing a small set of tools for a mock **order management** backend and optionally a mock **inventory** backend.  
- **eComBot v5** configured to treat that MCP server as a tool provider and call its tools in real support flows (for example, order status and stock checks).  
- Clear handling of **common error cases** such as timeouts and not‑found responses, with user‑friendly messages.  
- A few simple tests or scripts that you can rerun to validate eComBot’s tool behaviour and error handling.

## 4. Core tasks

### Task 4.1 – Create a FastMCP server skeleton for eComBot

Goal: Set up a basic FastMCP server process in your repo for eComBot’s backend integrations.

Steps:

1. Under `src/services/`, create a new module or package for your MCP server (for example, `orders_server/`).  
2. Initialise a minimal FastMCP server entrypoint that can start, accept connections, and shut down cleanly.  
3. Add any basic configuration you need (for example, port, transport choice) and wire it through your existing config helpers in `src/config/`.  
4. Run the server and confirm it starts without errors and is reachable by a simple MCP client or health check.

Checkpoint:

- You can start and stop your FastMCP orders server from the command line.  
- Logs confirm that the server is running and ready to accept MCP client connections.

---

### Task 4.2 – Design and register order tools for eComBot

Goal: Expose a small set of **order‑related tools** through your FastMCP server and make them suitable for eComBot’s support flows.

Steps:

1. Decide on two or three operations that make sense for an e‑commerce order backend, such as:  
   - `get_order_status` – given an order ID, return status and key details.  
   - `get_order_details` – given an order ID, return item‑level details.  
   - `cancel_order` – cancel a specific order if allowed.  
2. For each operation, define clear input parameters and expected outputs. Keep operations focused and idempotent where possible.  
3. Implement these operations as Python functions in your FastMCP orders server module and register them as MCP tools.  
4. Add simple in‑memory data (for example, a small dictionary of orders) so that your tools can return realistic responses.  
5. Restart the FastMCP server and use an MCP client or debug script to list available tools and call each one once.

Checkpoint:

- Your orders server lists the tools you defined.  
- Calling each tool with valid input returns structured data as expected.  
- Calling a tool with clearly invalid input returns a controlled error or not‑found result.

---

### Task 4.3 – Add inventory tools (optional but recommended)

Goal: Add a small set of **inventory‑related tools** so eComBot can answer stock and product availability questions using FastMCP.

Steps:

1. Define one or two tools for a simple inventory backend, such as:  
   - `check_stock` – given a product ID or SKU, return stock level or availability.  
   - `list_variants` – given a product family, return available variants (for example, colours, storage sizes).  
2. Decide whether these live in the same FastMCP server as your order tools or in a second server module; keep your layout simple and clear.  
3. Implement these tools with small, fake datasets that mimic real‑world responses (for example, a few products and stock counts).  
4. Register the tools and confirm they appear in your tool listing and can be called independently.

Checkpoint:

- Both order tools and inventory tools are registered and callable.  
- You can distinguish them by name and purpose when you inspect the tool list.

---

### Task 4.4 – Wire FastMCP tools into eComBot

Goal: Make eComBot aware of the new MCP tools and able to call them in response to user queries.

Steps:

1. Locate the part of eComBot’s configuration where tools are registered or injected (for example, in `src/agents/support_agent.py` or a tools registry).  
2. Add a configuration section that points to your FastMCP orders (and inventory) server and describes which tools should be exposed to eComBot.  
3. Update eComBot’s system prompt or instructions to describe these new capabilities in plain language (for example, that the support agent can call order and inventory tools to fetch live‑style data).  
4. Run eComBot through ADK Web or your existing entrypoint and issue test queries that should trigger:  
   - Order tools (for example, “Where is my order #12345?”).  
   - Inventory tools (for example, “Do you have the Pixel 9 Pro in stock in black?”).  
5. Use logs or traces to confirm that tool calls are being made through the MCP client and that responses are being incorporated into eComBot’s replies.

Checkpoint:

- eComBot calls order tools when asked about orders and inventory tools when asked about stock or variants.  
- Tool outputs appear to inform the answer rather than eComBot guessing.

---

### Task 4.5 – Handle common error scenarios in eComBot

Goal: Make your FastMCP integration resilient to timeouts, not‑found errors, and server failures, while keeping eComBot’s user messaging clear.

Steps:

1. Identify how your MCP client layer reports different error conditions (for example, timeout, not‑found, or internal server error).  
2. In eComBot’s integration layer or support agent code, add handling branches for at least two cases:  
   - When an order or inventory tool returns a not‑found result (for example, unknown order ID or product).  
   - When a tool call fails due to timeout or an internal error.  
3. For each case, decide what the user‑facing message should look like so that it is honest and helpful without exposing raw error details.  
4. Temporarily configure your FastMCP server to simulate these errors (for example, by using special IDs or inducing a delay) and run test queries through eComBot.  
5. Confirm that eComBot’s responses in error conditions match your intended messages.

Checkpoint:

- Not‑found cases lead to clear, non‑hallucinated responses (for example, asking the user to check the order or product identifier).  
- Timeout or failure cases lead to a graceful fallback description rather than a crash or confusing output.

---

### Task 4.6 – Add basic verification or tests for eComBot

Goal: Capture the expected tool behaviours and error handling in repeatable checks for eComBot.

Steps:

1. Define three to five representative test inputs that exercise:  
   - A successful `get_order_status` call via eComBot.  
   - A successful `check_stock` or `list_variants` call via eComBot (if implemented).  
   - An order not‑found scenario.  
   - A simulated timeout or server failure.  
2. For each test, write down the expected high‑level behaviour (which tool should be called and the kind of message the user should receive).  
3. Implement these checks in the `tests/` folder, or as a script that sends queries to eComBot and inspects logs or structured outputs.  
4. Run the tests and adjust your implementation until they pass reliably.  
5. Commit your changes together with the tests so that future refactors can be validated quickly.

Checkpoint:

- You have at least a small suite of tests demonstrating that eComBot’s FastMCP integration works and fails in controlled ways.  
- You know how to rerun these tests when you modify tools or error handling.

## 5. Stretch tasks (optional)

These tasks are optional and intended for participants who finish the core lab early.

### Stretch 5.1 – Add simple input validation in eComBot flows

Goal: Prevent clearly invalid inputs from reaching tools, and provide early feedback to users.

Ideas:

- Add checks that order IDs follow a basic pattern before calling `get_order_status` or `cancel_order`.  
- Validate that product IDs or SKUs are non‑empty and correctly formatted before calling inventory tools.  
- Log validation failures separately from backend errors so you can see what users are trying to do.

### Stretch 5.2 – Separate servers for orders and inventory

Goal: Explore what it feels like to run separate MCP servers for different eComBot capability clusters.

Ideas:

- Keep order tools in one FastMCP server and inventory tools in another.  
- Configure eComBot to connect to both and verify that the right tools are called for each type of query.  
- Consider whether this separation makes it easier to evolve or deploy each backend independently.

## 6. Lab completion checklist

You can consider this lab complete when:

- You have at least one FastMCP server running under `src/services/` with order tools exposed for eComBot.  
- You have added at least one additional tool group (such as inventory tools) to the same or another server.  
- eComBot can call these tools in response to relevant user queries and incorporate their results into replies.  
- Common error cases (not‑found, timeout or failure) are handled in a way that keeps user messaging clear and honest.  
- You have at least a few tests or scripts that demonstrate the FastMCP integration working and failing in controlled ways.

Take a moment to note how your system has changed: eComBot’s external behaviour can now evolve by changing MCP servers and tool implementations, without rewriting core agent logic.
