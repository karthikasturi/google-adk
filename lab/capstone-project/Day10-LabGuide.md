# Day 10 Lab Guide – Generative UI with Chainlit (eComBot v7)

## 1. Lab overview

In this lab, you give **eComBot** a richer user interface using **Chainlit** instead of a plain chat box.
You will build a Chainlit-based UI that can reflect what eComBot is doing behind the scenes: which tools it calls, which agents are active, and what structured data it is returning.

## 2. Starting state – what you should already have

Before you start, confirm that your environment matches this starting state:

- A working **eComBot v6** with multi-agent orchestration in place (Orchestrator, Support Agent, Sales Agent).  
- Tools and RAG integrations working for order and product flows.  
- Repository structure similar to earlier days, for example:  
  - `src/agents/` – orchestrator, support, and sales agents.  
  - `src/tools/` – order, inventory, and utility tools.  
  - `src/services/` – FastMCP servers and other external integrations.  
  - `src/rag/` – RAG pipelines and index/query helpers.  
  - `src/ui/` – reserved for UI code (you will add Chainlit files here).  
  - `src/config/` – configuration helpers and environment loading.  
  - `tests/` – basic tests or scripts for support and sales flows.  
- A current stable version of **Chainlit** installed and importable in your Python environment.  

If any of these pieces are missing, align your environment before continuing.

## 3. Target state – what you will build

By the end of this lab, you should have:

- A Chainlit application that acts as the front end for eComBot.  
- UI behaviour that goes beyond plain chat by exposing:  
  - Basic messages and structured cards for key entities (for example, orders and products).  
  - Steps that visualise internal actions like tool calls.  
  - Actions (buttons) for user choices in common flows.  
  - Session state to keep context across multiple turns.  
- A small set of manual flows you can run to verify that the UI reflects eComBot’s behaviour clearly.

## 4. Core tasks

### Task 4.1 – Create a basic Chainlit entrypoint for eComBot

Goal: Wire Chainlit to send user messages to your existing Orchestrator and show simple responses.

Steps:

1. Under `src/ui/`, create a new Python module for the Chainlit app (for example, `chainlit_app.py`).  
2. In this module, import Chainlit and your Orchestrator agent entrypoint.  
3. Implement a minimal `@cl.on_message` handler that:  
   - Receives the user message.  
   - Calls the Orchestrator with the message content.  
   - Sends back a simple `cl.Message` with the Orchestrator’s final text reply.  
4. Start Chainlit using its recommended command for your environment and send a few test messages to confirm that eComBot responds end-to-end.

Checkpoint:

- You can chat with eComBot via Chainlit and get responses similar to your previous interface.  
- No UI enhancements yet, just a working baseline.

---

### Task 4.2 – Add structured cards for key entities

Goal: Represent important entities (such as orders and products) as structured UI elements instead of only text.

Steps:

1. Identify at least one support flow (for example, "Where is my order?") and one sales flow (for example, "Compare two phones").  
2. For each flow, decide what fields belong on a simple **card** (for example, order ID, status, ETA; or product name, price, key specs).  
3. Modify your Orchestrator or agents so that, when these flows run successfully, they return both:  
   - A natural-language summary.  
   - A structured object that matches your card schema.  
4. In your `chainlit_app.py`, update the message-sending code to:  
   - Render the summary as the main message content.  
   - Attach an element (for example, a JSON or table element) representing the card fields.  
5. Trigger the target flows through Chainlit and verify that you see both text and structured cards.

Checkpoint:

- At least one support-style and one sales-style flow now produce structured cards in the UI.  
- The card layouts match the fields you defined and are easy to scan.

---

### Task 4.3 – Expose tool calls as steps in the UI

Goal: Make key tool calls visible as **steps** so users can see when eComBot is doing real work.

Steps:

1. Choose a flow where the Support or Sales agent calls a tool (for example, order status lookup or product inventory check).  
2. Wrap the tool call in a Chainlit `@cl.step` (or equivalent) so that it appears as an expandable step in the UI.  
3. Ensure the step has a clear name (for example, "Check order status" or "Fetch product details") and a short description.  
4. Update your Orchestrator or agent invocation so that it awaits this step as part of handling the user request.  
5. Run the flow from Chainlit and watch for the step to appear when the tool runs.

Checkpoint:

- At least one flow shows a named step in the Chainlit UI while a tool call is running.  
- Expanding the step reveals a concise summary of what was done or what data was returned.

---

### Task 4.4 – Add actions (buttons) for common user choices

Goal: Give users a way to make simple choices without typing full prompts.

Steps:

1. Identify a flow where the agent usually asks a follow-up question with a small set of options, such as:  
   - Choosing a budget band for recommendations.  
   - Choosing between viewing order details or starting a return.  
2. Replace that free-form follow-up with a Chainlit message that includes `cl.Action` buttons representing the options.  
3. Implement corresponding `@cl.action_callback` handlers that:  
   - Record the user’s choice (for example, store it in the session if needed).  
   - Call the appropriate agent or tool for the next step.  
   - Send back updated messages or cards reflecting the choice.  
4. Exercise the flow and verify that clicking buttons drives the conversation without additional typing.

Checkpoint:

- A common follow-up decision is now expressed as buttons rather than free text.  
- The conversation continues smoothly when a button is clicked, and the UI reflects the new state.

---

### Task 4.5 – Use session state to maintain context across turns

Goal: Make the UI and backend share context so users don’t need to repeat themselves.

Steps:

1. Pick a multi-turn scenario where the user reasonably expects the system to "remember" something (for example, destination city, preferred price range, or current order ID).  
2. When that information first appears, store it in Chainlit’s user session (for example, using `cl.user_session.set`).  
3. On later turns, retrieve the stored values (for example, using `cl.user_session.get`) instead of asking the user to repeat them.  
4. Update your agents so they take session-backed context into account when formulating responses.  
5. Run a multi-turn conversation through Chainlit and verify that:  
   - The user is not asked for the same information again.  
   - The UI responses clearly reflect the remembered context.

Checkpoint:

- At least one scenario uses session state to carry information across turns.  
- The behaviour is visible in the UI (for example, hotel results that clearly match the previously selected city and dates).

---

### Task 4.6 – Validate the UI with representative eComBot flows

Goal: Confirm that the new UI supports real eComBot support and sales journeys.

Steps:

1. Define a short set of test journeys, such as:  
   - A support journey: checking order status, then starting a return.  
   - A sales journey: getting recommendations, refining by budget or feature, then viewing details.  
2. For each journey, write down which UI features should appear (cards, steps, actions, and session-backed context).  
3. Run each journey in Chainlit and confirm that:  
   - The UI shows the expected structured components and steps.  
   - It is clear which kind of work eComBot is doing at each stage.  
4. Note any points where the UI still feels like a plain chat log and consider whether an additional card, step, or action would help.  
5. Update your implementation where necessary and re-run the journeys.

Checkpoint:

- Both support and sales journeys feel easier to follow in the UI compared to a plain chat box.  
- You can map each UI element back to a meaningful part of eComBot’s internal behaviour.

## 5. Stretch tasks (optional)

These tasks are optional and intended for participants who finish the core lab early.

### Stretch 5.1 – Add a simple “how this answer was made” view

Goal: Give users an optional explanation of how a complex answer was produced.

Ideas:

- Add an action or toggle that, when invoked, shows a summary of the key steps (agents, tools, or RAG calls) involved in the last answer.  
- Use additional steps or a separate message to present this explanation without cluttering the main conversation.  
- Ensure the explanation uses user-friendly language rather than raw logs.

### Stretch 5.2 – Differentiate Support vs Sales segments visually

Goal: Make it obvious when the conversation is in a support mode versus a sales mode.

Ideas:

- Add small visual cues (for example, short labels or tags) to messages or cards based on which agent produced the response.  
- Experiment with subtle styling differences (for example, icons or section headers) that highlight the current context without overwhelming the user.  
- Ensure that multi-agent handoffs remain clear in the UI even over longer conversations.

## 6. Lab completion checklist

You can consider this lab complete when:

- eComBot responds through a Chainlit-based interface instead of a plain chat box.  
- Key support and sales flows display structured cards, not just text.  
- At least one tool call appears as a visible step in the UI.  
- At least one flow uses actions (buttons) to capture common user choices.  
- At least one multi-turn scenario uses session state so the user does not have to repeat the same information.  

At this point, eComBot v7 has a generative UI that better reflects what your agents and tools are doing, making complex behaviour easier to understand and iterate on.
