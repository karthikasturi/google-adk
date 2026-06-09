# Day 07 Lab Guide – LLM Gateway with LiteLLM and OpenRouter (eComBot v4)

## 1. Lab overview

In this lab, you will move your existing eComBot implementation behind a LiteLLM gateway so that all model calls flow through a single proxy endpoint instead of calling a provider directly. You will add basic routing between a "fast" model group and a "deep" model group, and configure fallback behaviour so the system remains usable when the primary model fails or degrades.

You will work entirely inside your existing repository structure and reuse your current eComBot v3 functionality (tools, state, and RAG). The focus is on **wiring and behaviour**, not on changing the business logic of eComBot.

## 2. Starting state – what you should already have

Before you start, confirm that your environment matches this starting state:

- A working eComBot v3 implementation with:  
  - Tools integrated (for example, order status and product lookup).  
  - Session state persisted with Redis.  
  - RAG working with ChromaDB and/or AWS OpenSearch.  
- eComBot is callable through ADK Web or a simple Python entrypoint.  
- Repository structure similar to:  
  - `src/agents/` – agent definitions (main eComBot agent, support/sales logic as it exists today).  
  - `src/tools/` – tool implementations.  
  - `src/config/` – configuration helpers and environment loading.  
  - `tests/` – at least a few basic tests or scripts you can run to verify behaviour.  
- Valid API keys and configuration for:  
  - OpenRouter (already used in earlier modules).  
  - LiteLLM installed and reachable from your environment, or ready to be started for this lab.

If any of these do not match, pause and align your environment before continuing.

## 3. Target state – what you will build

By the end of this lab, you should have:

- eComBot v4 running with **all LLM calls routed through a LiteLLM proxy endpoint**.  
- LiteLLM configured with at least two logical model groups, for example:  
  - `fast-faq` – lighter, cheaper model for simple queries.  
  - `deep-support` – more capable model for complex or high‑stakes queries.  
- A simple routing mechanism where the eComBot agent sends a hint (such as intent or complexity) that guides LiteLLM to choose between `fast-faq` and `deep-support`.  
- A fallback policy so that when the primary group fails or times out, **LiteLLM automatically switches to a backup group**, and eComBot still returns a useful response.  
- A small set of manual checks and automated tests that prove routing and fallback are working as expected.

## 4. Core Tasks

### Task 4.1 – Point eComBot at the LiteLLM proxy

Goal: Replace direct calls to a provider with calls to a LiteLLM proxy endpoint, without changing agent behaviour.

Steps:

1. Locate the component in your codebase that makes LLM API calls (for example, a client wrapper or configuration inside `src/config/`).  
2. Introduce a configuration option for the **LLM base URL** so you can switch between direct provider and LiteLLM proxy by changing configuration only.  
3. Update the configuration to point to your running LiteLLM proxy endpoint.  
4. Run a small set of existing eComBot queries (for example, "Where is my order?" and "What products do you have?") to confirm that responses still work through the proxy.  
5. Note any differences in latency or logging output and make sure errors are still handled gracefully.

Checkpoint:

- eComBot responds correctly to basic queries while calling the LiteLLM proxy instead of a provider endpoint.  
- Logs or console output confirm that requests are flowing through LiteLLM.

---

### Task 4.2 – Define fast and deep model groups in LiteLLM

Goal: Configure LiteLLM with at least two routes/model groups corresponding to "fast" and "deep" usage patterns.

Steps:

1. Open your LiteLLM configuration (file or admin UI) and create two logical groups, such as:  
   - `fast-faq` – mapped to a lighter, cheaper model suitable for FAQs and short responses.  
   - `deep-support` – mapped to a more capable model suitable for complex, multi‑step queries.  
2. Ensure both groups are configured to use OpenRouter (and optionally another provider if available) with the appropriate model names and settings.  
3. Configure any basic per‑group settings (such as maximum tokens or temperature) that fit the intended role of each group.  
4. Save the configuration and reload/restart the LiteLLM proxy if required.

Checkpoint:

- From a simple script or test, you can send a request that explicitly targets `fast-faq` and another that targets `deep-support` and see different model identifiers or behaviour in the LiteLLM logs.

---

### Task 4.3 – Add routing hints from the eComBot agent

Goal: Let the agent express simple hints (such as intent or complexity) so LiteLLM can choose the right model group.

Steps:

1. Identify where the agent currently determines intent or query type (for example, support vs sales, FAQ vs complex flow).  
2. Extend this logic to derive a small, explicit routing hint, such as:  
   - `route_hint = "fast-faq"` for simple FAQs and low‑risk queries.  
   - `route_hint = "deep-support"` for complex complaints, multi‑step problem solving, or ambiguous queries.  
3. Modify the payload sent to LiteLLM so that this `route_hint` is included in a field that LiteLLM routing can read (for example, metadata or a custom header, depending on your setup).  
4. Adjust your LiteLLM routing configuration so it uses `route_hint` to pick the appropriate model group for each request.  
5. Run several queries through eComBot to exercise both routes, and verify in the logs that the expected model group is chosen.

Checkpoint:

- Simple queries (such as a straightforward order status check) consistently use the `fast-faq` route.  
- Complex queries (such as multi‑item complaints or rich product comparisons) consistently use the `deep-support` route.  
- LiteLLM logs clearly show the chosen route for each request.

---

### Task 4.4 – Configure and test fallback behaviour

Goal: Ensure that when the primary route fails or times out, LiteLLM falls back to a secondary route and eComBot still returns a reasonable response.

Steps:

1. In the LiteLLM configuration, define a **fallback policy** for at least one of your groups (for example, `fast-faq` falls back to `deep-support`, or both fallback to a simpler general‑purpose model).  
2. Configure retry limits and error conditions that should trigger fallback (for example, specific error codes, timeouts, or provider‑level failures).  
3. Intentionally cause a failure on the primary route (for example, by temporarily misconfiguring the primary model name or pointing it to a non‑responsive test endpoint).  
4. Run a set of eComBot queries that would normally use the affected route and observe how LiteLLM handles the error and switches to the fallback group.  
5. Restore the primary route configuration and confirm that normal routing behaviour returns.

Checkpoint:

- When the primary route is healthy, eComBot uses it as expected.  
- When the primary route is unhealthy, LiteLLM retries within the configured limits and then switches to the fallback group.  
- eComBot continues to return meaningful responses during the failure, though they may be slightly different in style or detail.

---

### Task 4.5 – Add basic verification and tests

Goal: Capture your routing and fallback expectations in repeatable checks or tests.

Steps:

1. Create a small set of test inputs or scripts that represent:  
   - A simple FAQ query that should route to `fast-faq`.  
   - A complex support query that should route to `deep-support`.  
   - A scenario where the primary route is intentionally unhealthy and fallback should occur.  
2. For each test, record what you expect to see in terms of:  
   - Route selection (which group).  
   - Whether fallback should be used.  
   - Basic response quality (for example, must mention a specific key piece of information).  
3. Run the tests against your eComBot entrypoint and inspect LiteLLM logs or any structured output you have to confirm that the expectations are met.  
4. Optionally, capture these checks in your `tests/` folder as simple automated tests so you can rerun them quickly when you change routing or models.

Checkpoint:

- You have at least three concrete test cases that demonstrate routing and fallback behaviour end‑to‑end.  
- You know how to run these tests and interpret the results.

## 5. Stretch tasks (optional)

These tasks are optional and intended for participants who finish the core tasks early.

### Stretch 5.1 – Log route decisions for cost and latency awareness

Goal: Make it easier to reason about the cost and performance impact of your routing choices without building a full observability stack.

Ideas:

- Add a lightweight logging hook in your eComBot code that records which route was used, along with basic timing for each request.  
- After running a small batch of test queries, review the logs to see patterns in which routes are used most often and how long they take.  
- Note any obvious opportunities to move certain queries to a cheaper route or to tighten timeout thresholds.

### Stretch 5.2 – Experiment with alternative model choices

Goal: Explore how different models in your `fast-faq` and `deep-support` groups affect quality and cost.

Ideas:

- Swap one model in the `fast-faq` group for another lightweight model and rerun your tests.  
- Compare latency and response quality before and after the change.  
- Decide whether the new configuration is an improvement and, if so, keep it as your default.

## 6. Lab completion checklist

You can consider this lab complete when:

- eComBot calls a LiteLLM proxy endpoint for all LLM interactions.  
- LiteLLM has at least two model groups configured and in active use (`fast-faq` and `deep-support`, or equivalent).  
- The agent can influence routing via a simple hint (such as intent or complexity), and you can see the effect in practice.  
- Fallback behaviour is configured and verified by inducing a primary‑route failure and observing a successful switch to a backup route.  
- You have a small set of manual or automated tests that exercise routing and fallback behaviour.

Take a moment to reflect on where model choice now lives in your system. You have moved from hard‑coded provider calls to a configuration‑driven gateway, which will make future changes to models, providers, and routing policies more manageable.
