"""
app.py — Day 10: TravelBot Generative UI with Chainlit
=======================================================
Run:
    cp .env.example .env   # fill in OPENROUTER_API_KEY
    chainlit run app.py

Demonstrates six Chainlit UI patterns layered on top of the same
Google ADK multi-agent backend from previous days:

  Group 1 — Messages + elements   Itinerary response includes a
                                   structured day-by-day card element.
  Group 2 — Steps for tool calls  Every ADK tool call appears as an
                                   expandable Step in the Chainlit UI.
  Group 3 — Action buttons        Hotel search results include budget-
                                   filter buttons (budget / mid-range /
                                   premium) via cl.Action.
  Group 4 — Session state         cl.user_session persists destination
                                   and dates across turns so the user
                                   doesn't have to repeat them.
  Group 5 — Progress + errors     Multi-city planning shows one Step per
                                   city (5A); a simulated hotel-search
                                   failure shows a graceful error state (5B).
  Group 6 — Explainability        Typing "show me how you made this"
                                   summarises the agents, tools, and
                                   routing used in the last turn.

TRAINER DEMO PROMPTS
--------------------
Group 1A  "Plan a 3-day trip to Goa focused on beaches and local food."
Group 2A  "Check the status of my flight from Delhi to Singapore. Reference: DEL-SIN-202."
Group 3A  "Find me a hotel in Bangalore for this weekend near Indiranagar."
Group 4A  Turn 1: "I want to plan a trip to Tokyo in October."
          Turn 2: "Now show me budget hotel options within walking distance of Shibuya."
Group 5A  "Help me design a 7-day Europe itinerary covering Paris, Amsterdam, and Berlin."
Group 5B  Set SIMULATE_HOTEL_ERROR=1 in .env, restart, then:
          "Find me three hotel options in Rome near the Colosseum."
Group 6   After any rich response: "Show me how you came up with this plan."
"""

import json
import logging
import os
import re
from datetime import datetime, timezone

import chainlit as cl
import litellm
from dotenv import load_dotenv
from google.genai import types

load_dotenv()

logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False
litellm.suppress_debug_info = True

from agent import concierge_agent
from session import make_runner
from tools import search_hotels

# ── Helpers ──────────────────────────────────────────────────────────────────

_TOOL_LABELS = {
    "get_attractions": "Search attractions",
    "get_weather_forecast": "Get weather forecast",
    "get_booking_status": "Check flight status",
    "search_hotels": "Search hotels",
    "transfer_to_agent": "Route to specialist",
}

_EXPLAINABILITY_TRIGGERS = [
    "show me how", "how did you", "how was this", "how did this",
    "explain how", "walk me through",
]

_CITY_RE = re.compile(
    r"\b(Singapore|Goa|Tokyo|Dubai|Paris|Amsterdam|Berlin|Bangalore|"
    r"Rome|Delhi|Mumbai|Bengaluru|London|Bangkok|New York)\b",
    re.IGNORECASE,
)

_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|"
    r"October|November|December|this weekend|next week|tomorrow|"
    r"\d{1,2}/\d{1,2})\b",
    re.IGNORECASE,
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_explainability_query(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in _EXPLAINABILITY_TRIGGERS)


def _extract_context(text: str) -> dict:
    cities = _CITY_RE.findall(text)
    dates = _DATE_RE.findall(text)
    return {
        "destination": cities[0].title() if cities else None,
        "dates": dates[0] if dates else None,
    }


# ── Itinerary card builder (Group 1) ─────────────────────────────────────────

def _build_itinerary_card(attractions_resp: dict) -> str:
    """
    Build a Markdown table card from a raw get_attractions response.
    Returns empty string if the response has no usable data.
    """
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


# ── Hotel card builder (Group 3 / 5B) ────────────────────────────────────────

def _build_hotel_card(hotels_resp: dict, budget_filter: str = "") -> str:
    """
    Build a Markdown table from a raw search_hotels response.
    Returns an error note if the response contains an error.
    """
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


# ── Chainlit lifecycle ────────────────────────────────────────────────────────

@cl.on_chat_start
async def on_chat_start():
    """Group 4: initialise per-session state and ADK runner."""
    runner, user_id, session_id = await make_runner(concierge_agent)

    cl.user_session.set("runner", runner)
    cl.user_session.set("user_id", user_id)
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("destination", None)   # Group 4: remembered destination
    cl.user_session.set("travel_dates", None)  # Group 4: remembered dates
    cl.user_session.set("turn_log", [])        # Group 6: explainability history

    await cl.Message(
        content=(
            "Welcome to **TravelBot** ✈️\n\n"
            "I can help you with:\n"
            "- **Trip planning** – day-by-day itineraries and attraction cards\n"
            "- **Flight status** – look up your booking reference\n"
            "- **Hotel search** – find and filter by budget\n\n"
            "Type a request to get started, or try one of the demo prompts "
            "from the trainer guide."
        )
    ).send()


# ── Core ADK runner + Chainlit step mapper ────────────────────────────────────

async def _run_turn(prompt: str) -> dict:
    """
    Send one turn to the ADK agent and map events to Chainlit UI.

    Returns a summary dict:
        text            — agent's final reply text
        author          — name of the agent that produced the reply
        tool_responses  — {tool_name: response_dict} for each tool called
        transfers       — list of "from → to" strings for transfer_to_agent hops
        has_error       — True if any tool returned an error dict
    """
    runner = cl.user_session.get("runner")
    user_id = cl.user_session.get("user_id")
    session_id = cl.user_session.get("session_id")

    open_steps: dict[str, cl.Step] = {}
    tool_responses: dict[str, dict] = {}
    transfers: list[str] = []
    final_text = ""
    final_author = ""
    has_error = False

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:

                # ── Tool call → open a Chainlit Step (Group 2 / 5A) ─────────
                if fc := getattr(part, "function_call", None):
                    args = dict(fc.args or {})

                    if fc.name == "transfer_to_agent":
                        target = args.get("agent_name", "specialist")
                        transfers.append(f"{event.author} → {target}")
                        step = cl.Step(name=f"Routing to {target}", type="tool")
                    else:
                        label = _TOOL_LABELS.get(fc.name, fc.name.replace("_", " ").title())
                        step = cl.Step(name=label, type="tool")
                        step.input = json.dumps(args, indent=2)

                    await step.send()
                    open_steps[fc.name] = step

                # ── Tool response → close the Step ────────────────────────────
                if fr := getattr(part, "function_response", None):
                    if fr.name in open_steps:
                        step = open_steps.pop(fr.name)
                        resp = fr.response or {}

                        if fr.name == "transfer_to_agent":
                            step.output = "Transferred"
                        else:
                            is_err = isinstance(resp, dict) and "error" in resp
                            step.output = f"```json\n{json.dumps(resp, indent=2)}\n```"
                            step.is_error = is_err
                            if is_err:
                                has_error = True
                            tool_responses[fr.name] = resp

                        step.end = _utcnow()
                        await step.update()

        # ── Final response ────────────────────────────────────────────────────
        if event.is_final_response() and event.content and event.content.parts:
            text = event.content.parts[0].text
            if text:
                final_text = text
                final_author = event.author

    return {
        "text": final_text.strip(),
        "author": final_author,
        "tool_responses": tool_responses,
        "transfers": transfers,
        "has_error": has_error,
    }


# ── Message handler ───────────────────────────────────────────────────────────

@cl.on_message
async def on_message(message: cl.Message):
    prompt = message.content.strip()

    # ── Group 6: Explainability ───────────────────────────────────────────────
    if _is_explainability_query(prompt):
        await _send_explainability()
        return

    # ── Group 4: Update session context ──────────────────────────────────────
    ctx = _extract_context(prompt)
    if ctx["destination"]:
        cl.user_session.set("destination", ctx["destination"])
    if ctx["dates"]:
        cl.user_session.set("travel_dates", ctx["dates"])

    # ── Run the ADK turn (Groups 1–5) ────────────────────────────────────────
    result = await _run_turn(prompt)

    if not result["text"]:
        return

    # cl.Message.content is rendered as markdown; cards are appended directly
    # so tables and headings render properly (cl.Text with language= shows raw
    # source in a code block, which is wrong for formatted output).
    content = result["text"]
    actions: list[cl.Action] = []

    # ── Group 1: Itinerary card appended to message content ──────────────────
    if "get_attractions" in result["tool_responses"]:
        card_md = _build_itinerary_card(result["tool_responses"]["get_attractions"])
        if card_md:
            content += f"\n\n---\n\n{card_md}"

    # ── Group 3: Hotel card + budget filter action buttons ────────────────────
    if "search_hotels" in result["tool_responses"]:
        hotel_resp = result["tool_responses"]["search_hotels"]
        city = hotel_resp.get("city", cl.user_session.get("destination") or "")

        hotel_md = _build_hotel_card(hotel_resp)
        if hotel_md:
            content += f"\n\n---\n\n{hotel_md}"

        # Budget filter buttons only when the search succeeded
        if not result["has_error"] and hotel_resp.get("found"):
            actions = [
                cl.Action(
                    name="hotel_filter",
                    payload={"city": city, "budget": "budget", "nights": hotel_resp.get("nights", 2)},
                    label="Budget",
                    tooltip="Show budget options (lowest price tier)",
                ),
                cl.Action(
                    name="hotel_filter",
                    payload={"city": city, "budget": "midrange", "nights": hotel_resp.get("nights", 2)},
                    label="Mid-range",
                    tooltip="Show mid-range options",
                ),
                cl.Action(
                    name="hotel_filter",
                    payload={"city": city, "budget": "premium", "nights": hotel_resp.get("nights", 2)},
                    label="Premium",
                    tooltip="Show premium options",
                ),
            ]

    # ── Send the enriched response message ────────────────────────────────────
    await cl.Message(content=content, actions=actions).send()

    # ── Group 4: Show context reminder when a new destination is detected ─────
    if ctx["destination"]:
        dest = cl.user_session.get("destination")
        dates = cl.user_session.get("travel_dates")
        note = f"📍 **Destination saved:** {dest}"
        if dates:
            note += f" · {dates}"
        note += " — I'll remember this for follow-up questions."
        await cl.Message(content=note, author="TravelBot Session").send()

    # ── Group 6: Append to turn log ──────────────────────────────────────────
    turn_log = cl.user_session.get("turn_log", [])
    turn_log.append({
        "query": prompt[:70],
        "agent": result["author"],
        "tools": list(result["tool_responses"].keys()),
        "routing": result["transfers"],
        "has_card": "get_attractions" in result["tool_responses"] or "search_hotels" in result["tool_responses"],
        "has_actions": bool(actions),
        "has_error": result["has_error"],
    })
    cl.user_session.set("turn_log", turn_log)


# ── Group 3: Hotel budget filter callback ─────────────────────────────────────

@cl.action_callback("hotel_filter")
async def on_hotel_filter(action: cl.Action):
    """
    Called when the user clicks a budget-tier button (Budget / Mid-range /
    Premium). Runs search_hotels directly (no ADK round-trip needed) and
    sends updated results as a new message with a card element.
    """
    city = action.payload.get("city", "")
    budget = action.payload.get("budget", "")
    nights = action.payload.get("nights", 2)

    # Show a step for the filtered search (Group 2 pattern inside action)
    async with cl.Step(name=f"Filter hotels — {budget}", type="tool") as step:
        step.input = json.dumps({"city": city, "budget_category": budget, "nights": nights}, indent=2)
        resp = search_hotels(city=city, budget_category=budget, nights=nights)
        step.output = f"```json\n{json.dumps(resp, indent=2)}\n```"
        if "error" in resp:
            step.is_error = True

    card_md = _build_hotel_card(resp, budget_filter=budget)
    tier_label = {"budget": "Budget", "midrange": "Mid-range", "premium": "Premium"}.get(budget, budget)
    city_label = city or "the requested city"

    await cl.Message(
        content=(
            f"Here are the **{tier_label}** hotel options in {city_label}:"
            f"\n\n---\n\n{card_md}"
        )
    ).send()


# ── Group 6: Explainability summary ──────────────────────────────────────────

async def _send_explainability():
    """
    Summarises how TravelBot produced the last response: which agents ran,
    which tools were called, how routing happened, and what UI elements were
    attached. Triggered when the user asks 'show me how you made this'.
    """
    turn_log: list[dict] = cl.user_session.get("turn_log", [])

    if not turn_log:
        await cl.Message(
            content="No turns recorded yet. Ask TravelBot something first, then try again."
        ).send()
        return

    last = turn_log[-1]
    lines = ["## How TravelBot built the last response", ""]

    lines += [
        f"**Agent that answered:** `{last['agent']}`",
        "",
    ]

    if last["routing"]:
        lines += [
            f"**Routing chain:** {' → '.join(r for r in last['routing'])}",
            "*(concierge_agent used `transfer_to_agent` to pass the turn)*",
            "",
        ]

    if last["tools"]:
        lines += [
            f"**Tools called:** {', '.join(f'`{t}`' for t in last['tools'])}",
            "*(each tool call appeared as an expandable Step in the UI)*",
            "",
        ]
    else:
        lines += ["**Tools called:** none — answered directly from conversation context", ""]

    ui_features = []
    if last["has_card"]:
        ui_features.append("a structured card element (`cl.Text` attached to the message)")
    if last["has_actions"]:
        ui_features.append("budget filter action buttons (`cl.Action`)")
    if last["has_error"]:
        ui_features.append("a tool error step (shown in red in the Step UI)")

    if ui_features:
        lines += [
            "**UI elements added by the app layer:**",
            *[f"  - {f}" for f in ui_features],
            "",
        ]

    if len(turn_log) > 1:
        lines += ["**All turns this session:**", ""]
        for i, entry in enumerate(turn_log, 1):
            tools_str = ", ".join(f"`{t}`" for t in entry["tools"]) if entry["tools"] else "direct answer"
            badge = " ⚠️" if entry["has_error"] else ""
            lines.append(
                f"{i}. [{entry['agent']}]{badge} \"{entry['query']}…\" — {tools_str}"
            )

    dest = cl.user_session.get("destination")
    dates = cl.user_session.get("travel_dates")
    if dest or dates:
        lines += ["", "**Session context (Group 4 — `cl.user_session`):**"]
        if dest:
            lines.append(f"  - Destination: {dest}")
        if dates:
            lines.append(f"  - Dates: {dates}")

    await cl.Message(content="\n".join(lines)).send()
