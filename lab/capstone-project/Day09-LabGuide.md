# Day 09 Lab Guide – Multi‑Agent Orchestration (eComBot v6)

## 1. Lab overview

In this lab, you transform your **single‑agent eComBot** into a **multi‑agent system** with an Orchestrator, Support Agent, and Sales Agent.
You will refactor existing logic, define clear responsibilities for each agent, and add enough tracing so you can see how delegation and handoff work end‑to‑end.

## 2. Starting state – what you should already have

Before you start, confirm that your environment matches this starting state:

- A working **single‑agent eComBot** that can:  
  - Answer basic support questions using tools and FastMCP (for example, order status and inventory checks).  
  - Answer basic sales questions using RAG (for example, product comparisons and recommendations).  
  - Route model calls through your LiteLLM gateway.  
- Repository structure similar to earlier days, for example:  
  - `src/agents/` – currently contains a single primary agent definition for eComBot.  
  - `src/tools/` – order, inventory, and utility tools.  
  - `src/services/` – FastMCP servers and other external integrations.  
  - `src/rag/` – RAG pipelines and index/query helpers.  
  - `src/config/` – configuration helpers and environment loading.  
  - `tests/` – basic tests or scripts to exercise support and sales flows.  
- You can run eComBot through ADK Web or an equivalent entrypoint and send it user queries.

If any of these pieces are missing, align your environment before continuing.

## 3. Target state – what you will build

By the end of this lab, you should have:

- An **Orchestrator Agent** that receives all user messages, classifies intent, and delegates work.  
- A **Support Agent** focused on order‑centric flows (for example, status, returns, complaints), reusing existing tools and RAG where needed.  
- A **Sales Agent** focused on sales‑centric flows (for example, recommendations, comparisons), reusing existing tools and RAG.  
- Routing logic that chooses between Support and Sales agents for common queries like:  
  - “Where is my order?”  
  - “Can you help me compare two phones?”  
- Traces or logs that make it clear which agent handled which part of each conversation.

## 4. Core tasks

### Task 4.1 – Extract Support and Sales responsibilities from the single agent

Goal: Define what belongs to Support vs Sales before you create new agents.

Steps:

1. Review your current single eComBot agent and list the types of questions it handles today.  
2. Group these into **support‑style** problems (order tracking, returns, issues) and **sales‑style** problems (recommendations, comparisons, up‑sell).  
3. For each group, note which tools and RAG sources they use (for example, order tools vs product catalog RAG).  
4. Write down a short description for each future agent:  
   - Support Agent: what it is responsible for and which tools/data it owns.  
   - Sales Agent: what it is responsible for and which tools/data it owns.  

Checkpoint:

- You have written descriptions and rough boundaries for Support vs Sales responsibilities.  
- You can point to at least one existing flow that will migrate to each agent.

---

### Task 4.2 – Create Support and Sales agent definitions

Goal: Implement separate Support and Sales agents that each handle their own domain.

Steps:

1. Under `src/agents/`, create separate modules for your new agents (for example, `support_agent.py` and `sales_agent.py`).  
2. Copy or refactor the relevant parts of your original eComBot prompts and configuration into these new agents, so that:  
   - Support Agent focuses on order issues and uses order/inventory tools plus any needed RAG.  
   - Sales Agent focuses on product discovery and uses product catalog RAG plus any sales‑relevant tools.  
3. Make sure each agent has:  
   - A clear system prompt that explains its scope and what kinds of questions it should answer.  
   - Access only to the tools and data it needs for its responsibilities.  
4. Write a small direct test for each agent (for example, a script or a test function) that sends a domain‑specific question and confirms it returns a sensible answer on its own.

Checkpoint:

- You can run the Support Agent and Sales Agent in isolation and get responses appropriate to their domains.  
- Tools and RAG usage for each agent match the responsibilities you defined earlier.

---

### Task 4.3 – Implement the Orchestrator Agent

Goal: Create an Orchestrator that receives user input and decides which agent to delegate to.

Steps:

1. Under `src/agents/`, add a module for the Orchestrator (for example, `orchestrator.py`).  
2. Design a prompt for the Orchestrator that:  
   - Explains that its job is to interpret user messages and decide whether they are **support‑centric**, **sales‑centric**, or trivial.  
   - Describes when it should call the Support Agent, when it should call the Sales Agent, and when it can answer directly.  
3. Implement a simple intent classification or routing mechanism, such as:  
   - Pattern‑based routing on phrases like “order”, “delivery”, “refund” vs “recommend”, “compare”, “buy”.  
   - Or a small LLM‑based classifier that returns a routing decision (support, sales, or self‑answer).  
4. Wire the Orchestrator so that it can:  
   - Call the Support Agent for support decisions.  
   - Call the Sales Agent for sales decisions.  
   - Respond directly for basic capability or meta questions.  

Checkpoint:

- The Orchestrator can receive a message, choose a target agent, and return the chosen agent’s reply to the user.  
- You can see routing decisions in your logs or trace output.

---

### Task 4.4 – Route real eComBot flows through the Orchestrator

Goal: Move your existing eComBot entrypoint so that all user messages pass through the Orchestrator.

Steps:

1. Locate the current entrypoint for eComBot (for example, the agent registered with ADK Web).  
2. Replace the single agent with the Orchestrator as the **primary entry agent** for user messages.  
3. Run the following queries through your usual interface and observe what happens:  
   - “Where is my order #12345?”  
   - “Can you recommend a phone under ₹30,000 for gaming?”  
   - “What can you help me with as a shopping assistant?”  
4. Check logs or traces to confirm that:  
   - Support‑style questions are handled by the Support Agent.  
   - Sales‑style questions are handled by the Sales Agent.  
   - Meta questions may be answered by the Orchestrator itself.  

Checkpoint:

- eComBot v6 (through the Orchestrator) still answers support and sales questions correctly.  
- You can see which agent handled each test query.

---

### Task 4.5 – Implement a basic Planner–Executor flow

Goal: Support a single request that requires both support and sales work, using a Planner–Executor style.

Steps:

1. Choose a realistic mixed scenario, such as:  
   - “My phone order was delayed, can you check its status and also suggest an alternative model that’s in stock?”  
2. Extend the Orchestrator logic so that it can:  
   - Recognise when a message contains both a **support task** and a **sales task**.  
   - Treat them as two sub‑tasks to run in sequence: first Support Agent, then Sales Agent.  
3. Implement a simple Planner mechanism inside the Orchestrator, for example:  
   - Extract the order‑related part and send it to the Support Agent.  
   - Use the Support Agent’s result (for example, delayed/cancelled status) as context when calling the Sales Agent for recommendations.  
4. Test the mixed scenario and verify that the final answer:  
   - Reports the order status clearly.  
   - Offers a relevant recommendation (for example, similar products that are available).  

Checkpoint:

- Mixed queries trigger both Support and Sales Agents in the intended order.  
- The Sales Agent appears to use context produced by the Support Agent, not just the original user text.

---

### Task 4.6 – Add minimal tracing for delegation and handoff

Goal: Make it easy to see which agent handled which part of a conversation.

Steps:

1. Decide where to record trace information (for example, structured logs, ADK Dev UI traces, or a simple in‑memory log for debugging).  
2. For each Orchestrator decision, log at least:  
   - The incoming user message.  
   - The routing decision (support, sales, self‑answer, or mixed).  
   - Which agent was called and with what high‑level task description.  
3. For each agent response, log a short summary of what was done (for example, “Support Agent: checked order status via get_order_status tool”).  
4. Run a short multi‑turn conversation that includes:  
   - A support query.  
   - A sales query.  
   - A mixed query.  
5. Inspect traces or logs and confirm that you can reconstruct the sequence of orchestration and delegation decisions.

Checkpoint:

- For any test conversation, you can answer: “Which agent handled each turn, and why did the Orchestrator choose that agent?”  
- You have enough trace information to debug mis‑routing or unexpected behaviour.

## 5. Stretch tasks (optional)

These tasks are optional and intended for participants who finish the core lab early.

### Stretch 5.1 – Add a verification loop for high‑risk answers

Goal: Use a second agent to review certain answers before they reach the user.

Ideas:

- Add a lightweight **Reviewer Agent** that only checks answers for a subset of flows (for example, refund policies or high‑value orders).  
- Configure the Orchestrator so that when a Support or Sales Agent answers in those flows, the Reviewer Agent is called to critique or approve the answer.  
- Log when a response is modified or rejected by the Reviewer.

### Stretch 5.2 – Fine‑tune routing rules

Goal: Improve routing quality beyond basic keyword checks.

Ideas:

- Replace simple keyword routing with a small LLM‑based classifier that labels messages as support, sales, mixed, or other.  
- Add tests that verify routing decisions for edge cases, such as “I want to buy something but my last order was cancelled.”  
- Track routing decisions over time to see where the Orchestrator is uncertain or making mistakes.

## 6. Lab completion checklist

You can consider this lab complete when:

- You have separate Support and Sales agents implemented under `src/agents/`.  
- An Orchestrator agent acts as the entrypoint, routing user queries to Support or Sales agents or answering trivial questions directly.  
- Mixed queries are handled using a Planner–Executor style flow that calls both Support and Sales agents in sequence.  
- You can inspect traces or logs to see which agent handled each part of a conversation and how delegation decisions were made.  

At this point, eComBot v6 behaves more like a **team of collaborating agents** than a single monolithic agent, which sets you up for richer UI and observability in later sessions.
