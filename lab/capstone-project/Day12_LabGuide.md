# Day 12 Lab Guide — Reasoning Patterns and Observability

## eComBot v9–v10 with Chainlit UI

### Lab Summary

In this lab, you will upgrade the Sales Agent with a ReAct-style reasoning loop so it can work through product recommendations step by step instead of answering in one pass. You will also wire LangSmith tracing into the system and create a PromptFoo evaluation suite that checks the core support and sales flows. By the end, you should be able to inspect a reasoning panel in Chainlit, trace agent behaviour end-to-end, and run a repeatable eval set that highlights routing, reasoning, and quality issues.

---

### Starting State

- eComBot v8 or at least v7 is already working with the Orchestrator, Support Agent, and Sales Agent.
- Chainlit is the active UI, not Gradio.
- `src/agents/sales_agent.py` exists and handles recommendation queries.
- LangSmith credentials are available in your environment.
- PromptFoo is available in your toolchain for running evaluation cases.
- `src/ui/` contains the Chainlit app entrypoint, or a similar UI module you can extend.

---

### Target State

- Sales Agent uses a reasoning loop to identify constraints, retrieve candidates, compare options, and recommend a result.
- If the user rejects a recommendation, the Sales Agent reflects on the rejection and adjusts the next pass.
- LangSmith traces show the orchestrator, sub-agents, tool calls, model usage, latency, and cost.
- PromptFoo has at least 10 test cases covering support, sales, edge cases, and negative cases.
- The Chainlit UI shows a collapsible reasoning panel or equivalent structured view for the agent’s reasoning steps.

---

### Core Task 1: Add a Reasoning Loop

**Goal:** Replace single-pass recommendation logic with a structured thought → action → observation loop.

**Steps:**
- Open `src/agents/sales_agent.py`.
- Find the current recommendation path and identify where the answer is produced in one pass.
- Refactor the logic so the agent first extracts constraints, then searches candidates, then compares them, then produces a final recommendation.
- Add a loop guard such as `max_iterations = 3` to prevent endless retries.
- Store each reasoning step in a structured format, such as a list of step records with a type and short description.

**Checkpoint:**
- Run a query like “I want a 4K TV under $500 with good reviews.”
- Confirm the response includes multiple reasoning steps before the final recommendation.
- Confirm the loop stops cleanly once a recommendation is formed.

---

### Core Task 2: Add Reflection on Rejection

**Goal:** Make the Sales Agent respond intelligently when the user rejects a recommendation.

**Steps:**
- Detect rejection phrases such as “too expensive,” “I said under X,” or “that doesn’t work.”
- Add a reflection step that records what constraint failed.
- Re-run the reasoning loop using the corrected constraint.
- Make sure the reflection step is visible in the structured reasoning output.

**Checkpoint:**
- Ask for a recommendation under a clear budget.
- Reject it with a message like “That’s over my budget.”
- Confirm the next response includes a reflection step and a corrected recommendation path.

---

### Core Task 3: Wire LangSmith Tracing

**Goal:** Capture agent routing, tool usage, latency, and cost for every run.

**Steps:**
- Add LangSmith configuration in `src/config/` or the existing config layer.
- Load keys from environment variables instead of hardcoding them.
- Attach tracing to the orchestrator so child agent calls are visible.
- Confirm tool calls and routed agent steps appear in the trace hierarchy.
- Make sure the trace includes enough metadata to tell which model handled the turn.

**Checkpoint:**
- Run a support query and a sales query.
- Open the traces and verify both show routing decisions and downstream steps.
- Confirm at least one trace includes a tool invocation or retrieval step.

---

### Core Task 4: Build an Eval Suite

**Goal:** Create a PromptFoo evaluation set that covers the important behaviours of the system.

**Steps:**
- Create a PromptFoo config in `tests/` or the agreed eval location.
- Add cases for support routing, sales recommendations, invalid IDs, budget rejection, and out-of-scope queries.
- Add assertions that check routing behaviour, response shape, and graceful fallback behaviour.
- Include a few negative cases to catch hallucinations or unsafe assumptions.
- Keep the suite small but representative.

**Checkpoint:**
- Run the eval suite.
- Confirm that the main success cases pass and that at least one negative case surfaces the expected failure mode.
- Verify that the suite is stable enough to rerun after prompt changes.

---

### Core Task 5: Surface Reasoning in Chainlit

**Goal:** Show the learner a structured view of what the agent is doing without exposing raw internal noise.

**Steps:**
- Open the Chainlit UI code in `src/ui/`.
- Add a collapsible or grouped UI area for reasoning steps.
- Render the reasoning list in a readable format, such as short labelled steps.
- Keep the main chat response concise while placing details in the reasoning panel.
- Preserve a fallback view if the agent returns unstructured output.

**Checkpoint:**
- Send a recommendation query in Chainlit.
- Confirm the UI shows the final answer and a separate reasoning view.
- Verify the view degrades gracefully if the reasoning payload is missing.

---

### Stretch Goals

- Add a second reasoning path for complex comparisons, such as comparing two products with trade-offs.
- Add a simple latency display in the Chainlit UI based on trace metadata.
- Expand the eval suite with more edge cases for ambiguous intent and invalid product constraints.
- Add a compact trace summary card in Chainlit that identifies the agent and model used.

---

### Completion Checklist

- Sales Agent uses a structured reasoning loop rather than a one-shot answer.
- Rejection handling triggers reflection and a revised recommendation.
- LangSmith traces show routing, tool calls, and timing details.
- PromptFoo covers at least 10 useful scenarios with a mix of positive and negative cases.
- Chainlit renders reasoning steps in a structured, readable way.
- The system still returns graceful fallbacks when data or structure is missing.
