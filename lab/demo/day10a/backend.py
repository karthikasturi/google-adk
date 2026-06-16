"""
backend.py — Day 10a: TravelBot FastAPI backend with streamable HTTP
====================================================================
Architecture:
    Gradio frontend (frontend.py, port 7860)
        |  HTTP chunked transfer — newline-delimited JSON (NDJSON)
        v
    FastAPI backend (this file, port 8000)
        |
        v
    ADK concierge_agent → trips / support / hotel specialists
        |
        v
    tools.py (mock data)

Endpoints:
    GET  /health                 Liveness check
    POST /sessions               Create an ADK agent session
    POST /chat/{session_id}      Run one turn; stream ADK events as NDJSON
    POST /hotels/filter          Filter hotels by budget tier (JSON, no ADK)

Stream format (application/x-ndjson) — one JSON object per line:

    {"type":"text_delta",  "content":"..."}              ← LLM token (StreamingMode.SSE)
    {"type":"step_start",  "name":"...", "input":"..."}  ← tool call begins
    {"type":"step_end",    "name":"...", "output":"...", "is_error":bool}
    {"type":"done", "text":"...", "author":"...",
     "card_md":"...", "hotel_card_md":"...",
     "has_hotels":bool, "hotel_city":"...", "hotel_nights":int, "has_error":bool}
    {"type":"error", "message":"..."}

Run:
    cd lab/demo/day10a
    cp .env.example .env          # fill in OPENROUTER_API_KEY
    pip install -r requirements.txt
    uvicorn backend:app --reload --port 8000
"""

import asyncio
import json
import logging
import os
import uuid

import litellm
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types
from pydantic import BaseModel

load_dotenv()

logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False
litellm.suppress_debug_info = True

from agent import concierge_agent  # noqa: E402  (after env setup)
from session import make_runner    # noqa: E402
from tools import search_hotels    # noqa: E402

# ── In-memory session store ───────────────────────────────────────────────────
_sessions: dict[str, dict] = {}
_sessions_lock = asyncio.Lock()

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="TravelBot API", version="1.0", description=__doc__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request models ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class FilterRequest(BaseModel):
    city: str
    budget: str
    nights: int = 2


# ── Tool display labels ───────────────────────────────────────────────────────
_TOOL_LABELS = {
    "get_attractions": "Search attractions",
    "get_weather_forecast": "Get weather forecast",
    "get_booking_status": "Check flight status",
    "search_hotels": "Search hotels",
    "transfer_to_agent": "Route to specialist",
}


# ── Markdown card builders ────────────────────────────────────────────────────

def _build_itinerary_card(attractions_resp: dict) -> str:
    """Build a Markdown day-by-day table from a get_attractions response."""
    city = attractions_resp.get("city", "")
    items = attractions_resp.get("attractions", [])
    days = int(attractions_resp.get("filters", {}).get("days") or 3)
    if not items:
        return ""

    lines = [f"### {city} — Attraction Overview", ""]
    lines.append("| Day | Attraction | Category |")
    lines.append("|-----|-----------|----------|")

    per_day = max(1, len(items) // days)
    for i, attr in enumerate(items):
        day = min(i // per_day + 1, days)
        lines.append(f"| Day {day} | {attr['name']} | {attr['category']} |")

    return "\n".join(lines)


def _build_hotel_card(hotels_resp: dict, budget_filter: str = "") -> str:
    """Build a Markdown table from a search_hotels response."""
    if "error" in hotels_resp:
        return f"⚠️ **Search failed:** {hotels_resp['error']}"

    items = hotels_resp.get("hotels", [])
    city = hotels_resp.get("city", "")
    nights = hotels_resp.get("nights", 2)
    tier = budget_filter or hotels_resp.get("filter", "all tiers")
    if not items:
        return f"No hotels found in **{city}** for the '{tier}' tier."

    label = f"### Hotels in {city}" + (f" — {tier.title()}" if budget_filter else "")
    lines = [label, ""]
    lines.append("| Hotel | Type | Per night | Neighbourhood | ⭐ |")
    lines.append("|-------|------|-----------|---------------|-----|")
    for h in items:
        price = f"₹{h['price_inr']:,}"
        lines.append(
            f"| {h['name']} | {h['category']} | {price} | {h['neighbourhood']} | {h['rating']} |"
        )
    if nights > 1:
        lines.append(f"\n*Showing {len(items)} option(s) · {nights}-night stay*")
    return "\n".join(lines)


# ── NDJSON helper ─────────────────────────────────────────────────────────────

def _chunk(data: dict) -> str:
    """Serialize a dict as one newline-delimited JSON line."""
    return json.dumps(data) + "\n"


# ── ADK streaming generator ───────────────────────────────────────────────────

async def _stream_adk(sess: dict, prompt: str):
    """
    Run one ADK turn and yield NDJSON lines for every meaningful event.

    Streaming semantics
    -------------------
    StreamingMode.SSE makes ADK call the LLM with stream=True, so the model
    yields token chunks as event.partial=True events. These become text_delta
    lines and the Gradio frontend appends each chunk to the chat bubble in
    real time.

    Tool calls are always yielded as complete events (ADK assembles function-
    call arguments from chunks internally), so step_start/step_end lines arrive
    in the same stream alongside the token deltas.

    Event order for a typical tool-using turn:
        step_start  (tool call begins)
        step_end    (tool returns)
        text_delta  (LLM generates response, token by token)
        text_delta  ...
        done        (complete text + card markdown for the frontend)
    """
    runner = sess["runner"]
    user_id = sess["user_id"]
    session_id = sess["session_id"]

    open_steps: dict[str, str] = {}    # tool_name → display label
    tool_responses: dict[str, dict] = {}
    transfers: list[str] = []
    final_text = ""
    final_author = ""
    has_error = False

    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            # Partial text token (LLM streaming) — emit immediately, skip tool-call checks
            if event.partial:
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if token := getattr(part, "text", None):
                            yield _chunk({"type": "text_delta", "content": token})
                continue

            if event.content and event.content.parts:
                for part in event.content.parts:

                    # Tool call → emit step_start immediately
                    if fc := getattr(part, "function_call", None):
                        args = dict(fc.args or {})
                        if fc.name == "transfer_to_agent":
                            target = args.get("agent_name", "specialist")
                            transfers.append(f"{event.author} → {target}")
                            label = f"Route to {target}"
                            input_str = ""
                        else:
                            label = _TOOL_LABELS.get(fc.name, fc.name.replace("_", " ").title())
                            input_str = json.dumps(args, indent=2)
                        open_steps[fc.name] = label
                        yield _chunk({"type": "step_start", "name": label, "input": input_str})

                    # Tool response → emit step_end
                    if fr := getattr(part, "function_response", None):
                        if fr.name in open_steps:
                            label = open_steps.pop(fr.name)
                            resp = fr.response or {}
                            if fr.name == "transfer_to_agent":
                                yield _chunk({"type": "step_end", "name": label,
                                            "output": "Transferred", "is_error": False})
                            else:
                                is_err = isinstance(resp, dict) and "error" in resp
                                if is_err:
                                    has_error = True
                                tool_responses[fr.name] = resp
                                yield _chunk({
                                    "type": "step_end",
                                    "name": label,
                                    "output": json.dumps(resp, indent=2),
                                    "is_error": is_err,
                                })

            # Final text response
            if event.is_final_response() and event.content and event.content.parts:
                text = event.content.parts[0].text
                if text:
                    final_text = text
                    final_author = event.author

        # Build cards and metadata for the frontend
        card_md = ""
        if "get_attractions" in tool_responses:
            card_md = _build_itinerary_card(tool_responses["get_attractions"])

        hotel_card_md = ""
        hotel_city = None
        hotel_nights = 2
        has_hotels = False
        if "search_hotels" in tool_responses:
            hotel_resp = tool_responses["search_hotels"]
            hotel_city = hotel_resp.get("city")
            hotel_nights = hotel_resp.get("nights", 2)
            has_hotels = hotel_resp.get("found", False) and not has_error
            hotel_card_md = _build_hotel_card(hotel_resp)

        yield _chunk({
            "type": "done",
            "text": final_text.strip(),
            "author": final_author,
            "card_md": card_md,
            "hotel_card_md": hotel_card_md,
            "has_hotels": has_hotels,
            "hotel_city": hotel_city,
            "hotel_nights": hotel_nights,
            "has_error": has_error,
        })

    except Exception as exc:
        yield _chunk({"type": "error", "message": str(exc)})


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/sessions")
async def create_session():
    """Create a new ADK agent session. Returns {session_id}."""
    session_id = str(uuid.uuid4())
    runner, user_id, adk_session_id = await make_runner(concierge_agent)
    async with _sessions_lock:
        _sessions[session_id] = {
            "runner": runner,
            "user_id": user_id,
            "session_id": adk_session_id,
        }
    return {"session_id": session_id}


@app.post("/chat/{session_id}")
async def chat(session_id: str, request: ChatRequest):
    """
    Send one message and receive a stream of SSE events.
    The response is application/x-ndjson; see module docstring for line format.
    """
    async with _sessions_lock:
        sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found. Start a new chat.")

    return StreamingResponse(
        _stream_adk(sess, request.message),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no"},  # disable nginx buffering
    )


@app.post("/hotels/filter")
async def filter_hotels(request: FilterRequest):
    """
    Run search_hotels directly (no ADK round-trip) and return formatted
    results as JSON including a pre-built Markdown card.
    """
    resp = search_hotels(city=request.city, budget_category=request.budget, nights=request.nights)
    card_md = _build_hotel_card(resp, budget_filter=request.budget)
    return {"result": resp, "card_md": card_md}
