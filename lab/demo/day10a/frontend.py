"""
frontend.py — Day 10a: TravelBot Gradio frontend
=================================================
Connects to the FastAPI backend (backend.py) via HTTP and SSE.

Architecture:
    This process (Gradio, port 7860)
        |  POST /sessions   → create ADK session
        |  POST /chat/{id}  → stream NDJSON events during each turn
        |  POST /hotels/filter → filter hotels (JSON, no streaming)
        v
    FastAPI backend (backend.py, port 8000)

UI features:
    - Chat history rendered as markdown (tables, headings in responses)
    - Live status bar showing which step is currently executing
    - Hotel budget filter buttons (Budget / Mid-range / Premium) that
      appear automatically after a hotel search
    - Session state tracks hotel city for filter callbacks

Run:
    # Terminal 1 — start backend first:
    uvicorn backend:app --reload --port 8000

    # Terminal 2 — start frontend:
    python frontend.py
    # Open http://localhost:7860

Demo prompts:
    Itinerary + card   "Plan a 3-day trip to Goa focused on beaches and local food."
    Flight status      "Check the status of my flight. Reference: DEL-SIN-202."
    Hotel + filter     "Find me a hotel in Bangalore near Indiranagar."
    Multi-city         "Design a 7-day Europe trip: Paris, Amsterdam, and Berlin."
    Error path         Set SIMULATE_HOTEL_ERROR=1 in .env, restart backend, then:
                       "Find me hotels in Rome near the Colosseum."
"""

import json
import os

import gradio as gr
import httpx

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")


# ── Session management ────────────────────────────────────────────────────────

async def _create_session() -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{API_BASE}/sessions")
        r.raise_for_status()
        return r.json()["session_id"]


# ── Chat streaming handler ────────────────────────────────────────────────────

async def _chat_stream(message: str, history: list, session_id, hotel_city, hotel_nights):
    """
    Send one message to the FastAPI backend and yield incremental UI updates.

    Yields: (history, session_id, status_md, hotel_row_update, hotel_city, hotel_nights)

    NDJSON lines from the backend drive the yield cadence:
      step_start → update status bar with current tool name
      step_end   → update status bar with ✅ / ❌ result
      done       → append full response (+ cards) to chat, show/hide hotel buttons
      error      → show error in chat
    """
    if not session_id:
        try:
            session_id = await _create_session()
        except Exception as exc:
            history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": f"⚠️ Cannot connect to TravelBot backend.\n\n`{exc}`\n\nMake sure `uvicorn backend:app --port 8000` is running."},
            ]
            yield history, session_id, "❌ Backend unreachable", gr.update(visible=False), hotel_city, hotel_nights
            return

    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": ""},
    ]
    h_city = hotel_city
    h_nights = int(hotel_nights or 2)

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{API_BASE}/chat/{session_id}",
                json={"message": message},
            ) as resp:
                resp.raise_for_status()

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    t = data.get("type")

                    if t == "text_delta":
                        history[-1]["content"] += data["content"]
                        yield history, session_id, "✍️ Generating…", gr.update(visible=False), h_city, h_nights

                    elif t == "step_start":
                        yield history, session_id, f"⚙️ {data['name']}…", gr.update(visible=False), h_city, h_nights

                    elif t == "step_end":
                        icon = "❌" if data.get("is_error") else "✅"
                        yield history, session_id, f"{icon} {data['name']}", gr.update(visible=False), h_city, h_nights

                    elif t == "done":
                        # Assemble response text with any embedded cards
                        text = data.get("text", "")
                        if data.get("card_md"):
                            text += f"\n\n---\n\n{data['card_md']}"
                        if data.get("hotel_card_md"):
                            text += f"\n\n---\n\n{data['hotel_card_md']}"
                        history[-1]["content"] = text

                        has_hotels = data.get("has_hotels", False)
                        h_city = data.get("hotel_city") or hotel_city
                        h_nights = data.get("hotel_nights", 2)
                        yield (
                            history,
                            session_id,
                            "✅ Ready",
                            gr.update(visible=has_hotels),
                            h_city,
                            h_nights,
                        )
                        break

                    elif t == "error":
                        history[-1]["content"] = f"⚠️ {data.get('message', 'Unknown error')}"
                        yield history, session_id, "❌ Error", gr.update(visible=False), h_city, h_nights
                        break

    except httpx.ConnectError:
        history[-1]["content"] = (
            "⚠️ Cannot reach TravelBot backend.\n\n"
            "Make sure `uvicorn backend:app --port 8000` is running in another terminal."
        )
        yield history, session_id, "❌ Backend unreachable", gr.update(visible=False), h_city, h_nights
    except Exception as exc:
        history[-1]["content"] = f"⚠️ Unexpected error: {exc}"
        yield history, session_id, "❌ Error", gr.update(visible=False), h_city, h_nights


# ── Hotel filter handlers ─────────────────────────────────────────────────────

async def _filter_hotels(budget: str, history: list, city, nights) -> tuple:
    """Call /hotels/filter and append the formatted card to the chat."""
    if not city:
        return history, "⚠️ No active hotel search — ask about hotels first"

    nights = int(nights or 2)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{API_BASE}/hotels/filter",
                json={"city": city, "budget": budget, "nights": nights},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        return history, f"❌ Filter failed: {exc}"

    card_md = data.get("card_md", "No results found.")
    tier = {"budget": "Budget", "midrange": "Mid-range", "premium": "Premium"}.get(budget, budget.title())
    new_history = history + [
        {"role": "user", "content": f"Show {tier} hotels"},
        {"role": "assistant", "content": f"**{tier} hotels in {city}:**\n\n---\n\n{card_md}"},
    ]
    return new_history, "✅ Ready"


async def _filter_budget(history, city, nights):
    return await _filter_hotels("budget", history, city, nights)

async def _filter_midrange(history, city, nights):
    return await _filter_hotels("midrange", history, city, nights)

async def _filter_premium(history, city, nights):
    return await _filter_hotels("premium", history, city, nights)


# ── Gradio UI ─────────────────────────────────────────────────────────────────

with gr.Blocks(title="TravelBot — Day 10a") as demo:

    # Per-session state
    session_id   = gr.State(None)
    hotel_city   = gr.State(None)
    hotel_nights = gr.State(2)

    gr.Markdown("""
# TravelBot ✈️
**Day 10a · FastAPI backend (SSE streaming) + Gradio frontend**

*The backend streams ADK workflow events as Server-Sent Events.
The status bar below the chat updates in real time as each tool executes.*
""")

    chatbot = gr.Chatbot(
        value=[],
        label="Chat",
        height=500,
        render_markdown=True,
    )

    status_md = gr.Markdown("✅ Ready")

    with gr.Row():
        msg_box = gr.Textbox(
            placeholder="Ask about itineraries, flights, or hotels…",
            show_label=False,
            scale=5,
            autofocus=True,
        )
        send_btn = gr.Button("Send", variant="primary", scale=1)

    # Hotel budget filter row — hidden until a hotel search completes
    with gr.Row(visible=False) as hotel_row:
        gr.Markdown("**Filter results by budget tier:**")
        btn_budget   = gr.Button("💰 Budget",    size="sm", variant="secondary")
        btn_midrange = gr.Button("🏨 Mid-range", size="sm", variant="secondary")
        btn_premium  = gr.Button("✨ Premium",   size="sm", variant="secondary")

    gr.Markdown("""
---
**Demo prompts — paste into the chat box above:**

| Scenario | Prompt |
|----------|--------|
| Itinerary card | *Plan a 3-day trip to Goa focused on beaches and local food.* |
| Flight status step | *Check the status of my flight. Reference: DEL-SIN-202.* |
| Hotel + budget buttons | *Find me a hotel in Bangalore near Indiranagar.* |
| Multi-city progress | *Design a 7-day Europe trip: Paris, Amsterdam, and Berlin.* |
| Error path | Set `SIMULATE_HOTEL_ERROR=1` in `.env`, restart backend, then ask about hotels in Rome. |

**Architecture** — what to observe:
- The **status bar** updates as each ADK tool call starts and completes (SSE streaming)
- **Cards** (itinerary tables, hotel tables) are built on the backend and sent in the `done` event
- **Budget buttons** appear automatically after a hotel search; clicking them calls `/hotels/filter` directly
- The Gradio frontend is a **pure HTTP client** — no ADK code runs here
""")

    # ── Event wiring ──────────────────────────────────────────────────────────

    _chat_inputs  = [msg_box, chatbot, session_id, hotel_city, hotel_nights]
    _chat_outputs = [chatbot, session_id, status_md, hotel_row, hotel_city, hotel_nights]

    msg_box.submit(
        _chat_stream, inputs=_chat_inputs, outputs=_chat_outputs,
    ).then(lambda: gr.update(value=""), outputs=msg_box)

    send_btn.click(
        _chat_stream, inputs=_chat_inputs, outputs=_chat_outputs,
    ).then(lambda: gr.update(value=""), outputs=msg_box)

    _filter_inputs  = [chatbot, hotel_city, hotel_nights]
    _filter_outputs = [chatbot, status_md]

    btn_budget.click(_filter_budget,   inputs=_filter_inputs, outputs=_filter_outputs)
    btn_midrange.click(_filter_midrange, inputs=_filter_inputs, outputs=_filter_outputs)
    btn_premium.click(_filter_premium,  inputs=_filter_inputs, outputs=_filter_outputs)


if __name__ == "__main__":
    demo.launch(server_port=7860, share=False, theme=gr.themes.Soft())
