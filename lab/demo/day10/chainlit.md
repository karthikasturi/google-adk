# TravelBot — Generative UI with Chainlit · Day 10

This demo shows how **Chainlit UI patterns** wrap the same Google ADK
multi-agent backend from previous days — making agent behaviour visible
and interactive without changing any backend code.

---

## Six Chainlit patterns demonstrated

| # | Pattern | Trigger prompt |
|---|---------|----------------|
| **1A** | Message + card element | *"Plan a 3-day trip to Goa focused on beaches and local food."* |
| **2A** | Steps for tool calls | *"Check the status of my flight DEL-SIN-202."* |
| **3A** | Action buttons (budget filter) | *"Find me a hotel in Bangalore near Indiranagar."* |
| **4A** | Session state across turns | Turn 1: *"I want to plan a trip to Tokyo in October."* → Turn 2: *"Now show me budget hotels near Shibuya."* |
| **5A** | Progress steps (multi-city) | *"Design a 7-day Europe itinerary: Paris, Amsterdam, Berlin."* |
| **5B** | Graceful error display | Set `SIMULATE_HOTEL_ERROR=1` then: *"Find hotels in Rome near the Colosseum."* |
| **6** | Explainability view | *"Show me how you came up with this plan."* |

---

## What to observe

- **Steps** (Groups 2, 3, 5): expand the tool-call blocks to see inputs and outputs.  
  Each `@cl.step` / `cl.Step` block corresponds to one ADK tool call.
- **Card elements** (Group 1): the structured table below the message text is a  
  `cl.Text(display="inline")` element built from the raw tool response — not from the LLM text.
- **Action buttons** (Group 3): clicking a budget tier calls the tool directly and  
  sends a new message with an updated card — no typed prompt needed.
- **Session context** (Group 4): the "📍 Destination saved" note confirms  
  `cl.user_session` is storing state. The second turn resolves the city from  
  ADK conversation history, not by the user repeating it.
- **Error state** (Group 5B): when `search_hotels` returns an error dict, the  
  tool step turns red and the agent sends a user-friendly fallback message.

---

## Architecture

```
Browser (Chainlit UI)
  └─ app.py   ← @cl.on_message maps ADK events → Steps / Elements / Actions
       └─ agent.py    ← concierge_agent + three sub_agents (ADK routing)
            └─ tools.py  ← get_attractions, get_booking_status, search_hotels …
```

The backend (agent.py + tools.py) is unchanged from previous days.
Everything visual is added in **app.py** using Chainlit's UI primitives.
