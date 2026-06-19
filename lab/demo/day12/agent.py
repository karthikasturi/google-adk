"""
agent.py — Day 12: TravelBot reasoning/eval agents
=====================================================
Two specialists behind a router, on two different model tiers — the
cost/latency teaching point in Scenario group 5:

  - support_specialist: cancellation policy + booking status. Cheap,
    single-lookup answers. Runs on the LITE model.
  - planner_specialist: flight search, comparison, and region-wide search.
    Multi-step ReAct-style reasoning (search → observe → broaden/refine).
    Runs on the CAPABLE model.

The "ReAct loop" here is the same mechanism every prior day already uses:
the ADK Runner keeps feeding tool results back to the model until it stops
calling tools, which IS Thought → Action → Observation. What's new in Day 12
is that we now *render* that loop (reasoning.py) and *trace* it (tracing.py)
instead of only showing the final answer.
"""

import logging
import os

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from tools import (
    compare_business_class,
    get_booking_status,
    get_cancellation_policy,
    search_cheapest_in_region,
    search_flights,
)

logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False
litellm.suppress_debug_info = True

load_dotenv()

CAPABLE_MODEL = "openrouter/google/gemini-2.5-flash"
LITE_MODEL = "openrouter/google/gemini-2.5-flash-lite"


# ── Planner specialist (capable model, multi-step reasoning) ────────────────

planner_specialist = LlmAgent(
    name="planner_specialist",
    model=LiteLlm(model=CAPABLE_MODEL),
    instruction="""
You are TravelBot's Planner. You search and compare flights using:
  - search_flights(origin, destination, max_budget_gbp, direct_only)
  - search_cheapest_in_region(region, max_budget_gbp, max_days_out)
  - compare_business_class(origin, destination)

Reasoning rules:
  - Always call a search tool before recommending anything — never invent
    a price, flight number, or schedule.
  - If the traveller doesn't give an origin city, assume London (TravelBot's
    home base) and say you're assuming that.
  - search_flights returns ALL matching flights, direct and connecting,
    regardless of budget. You must filter and reason over the results
    yourself: check direct flights against the budget first; if none fit,
    explicitly say so, then broaden to connecting flights and explain the
    tradeoff (cheaper but longer / more stops).
  - If the traveller corrects or changes a constraint they gave earlier in
    this conversation (e.g. now prioritising "direct" over "cheapest"),
    treat it as a real change: re-run the search reasoning with the new
    priority and acknowledge what changed before giving the new answer.
  - search_cheapest_in_region returns TravelBot's complete, finite set of
    known fares for that region in one call (`exhausted: true`). Once
    you've reasoned over that result, stop — do not call it again expecting
    a better answer; report the best feasible option(s) from what you have.
  - For business-class comparisons, weigh comfort (seat type, lounge
    access, legroom) against price — do not just recommend the cheapest
    option. State the tradeoff explicitly.
  - Keep the final answer to 1-2 short paragraphs: state the recommendation
    and the one or two facts that justify it.
""".strip(),
    description=(
        "Planner specialist — flight search, budget/comfort tradeoffs, and "
        "region-wide fare search."
    ),
    tools=[search_flights, search_cheapest_in_region, compare_business_class],
)


# ── Support specialist (lite model, single cheap lookups) ───────────────────

support_specialist = LlmAgent(
    name="support_specialist",
    model=LiteLlm(model=LITE_MODEL),
    instruction="""
You are TravelBot's Support specialist. You handle two kinds of request:
  - Cancellation/change policy questions → get_cancellation_policy(booking_type)
  - Booking status lookups → get_booking_status(booking_id)

Rules:
  - These are single-lookup answers — call the relevant tool once and
    answer directly. Do not search or reason over multiple options.
  - If the traveller asks about a booking but gives no reference, ask for
    one instead of guessing.
  - If a booking reference isn't found, say so plainly and ask them to
    double-check it.
  - Keep answers to 2-3 sentences.
""".strip(),
    description="Support specialist — cancellation policy and booking status lookups.",
    tools=[get_cancellation_policy, get_booking_status],
)


# ── Concierge (router, lite model — routing itself is a cheap decision) ─────

concierge_agent = LlmAgent(
    name="concierge_agent",
    model=LiteLlm(model=LITE_MODEL),
    instruction="""
You are TravelBot, a travel assistant. Route every request to the right
specialist. You have no tools yourself.

Routing:
  - Flight search, price/comfort comparisons, multi-city or budget
    tradeoffs → planner_specialist
  - Cancellation policy or booking status lookups → support_specialist

If the request is outside travel booking and planning (e.g. general
weather, unrelated trivia), say plainly that it's outside what TravelBot
can help with, and ask if there's a travel request you can help with
instead. Do not transfer for out-of-scope requests.
""".strip(),
    description="TravelBot concierge — routes to the Planner or Support specialist.",
    sub_agents=[planner_specialist, support_specialist],
)

root_agent = concierge_agent
