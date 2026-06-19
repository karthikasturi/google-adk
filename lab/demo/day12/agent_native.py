"""
agent_native.py — Day 12: framework-native ReAct (ADK PlanReActPlanner)
==========================================================================
The ADK-native counterpart to agent.py. Same TravelBot structure, but the
planner_specialist is given a `PlanReActPlanner`, so the *model itself*
emits an explicit, structured reasoning trace using ADK's tags:

    /*PLANNING*/      the plan it intends to follow
    /*REASONING*/     thoughts between steps
    /*ACTION*/        the tool call it's about to make
    /*REPLANNING*/    a revised plan when a constraint changes  ← real reflection
    /*FINAL_ANSWER*/  the answer shown to the user

This is the framework doing what reasoning.py does by hand. In particular
`/*REPLANNING*/` is genuine reflection emitted by the model — no keyword
heuristic (compare reasoning.py's `_REFLECTION_MARKERS`).

This file is additive: agent.py and the rest of the demo are unchanged. Run
it via demo_native.py, or point chainlit_app.py / demo.py at this module's
`root_agent` instead of agent.py's to see native reasoning in those.
"""

import logging
import os

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.planners import PlanReActPlanner

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


# ── Planner specialist — now with a framework-native ReAct planner ──────────
# The instruction no longer needs to *describe* the reasoning loop in prose;
# PlanReActPlanner enforces the plan → reason → act → (replan) → answer
# structure. We keep only the domain rules (what's true about the tools/data).

planner_specialist = LlmAgent(
    name="planner_specialist",
    model=LiteLlm(model=CAPABLE_MODEL),
    planner=PlanReActPlanner(),
    instruction="""
You are TravelBot's Planner. You search and compare flights using:
  - search_flights(origin, destination, max_budget_gbp, direct_only)
  - search_cheapest_in_region(region, max_budget_gbp, max_days_out)
  - compare_business_class(origin, destination)

Domain rules:
  - Never invent a price, flight number, or schedule — only use tool results.
  - search_flights returns ALL matching flights regardless of budget; check
    direct flights against the budget first, and if none fit, say so and
    broaden to connecting flights, explaining the tradeoff.
  - If the traveller doesn't give an origin, assume London and say so.
  - search_cheapest_in_region returns the complete finite set of known fares
    for a region in one call (`exhausted: true`) — reason over it once, then
    stop; do not re-query for a "better" answer.
  - For business class, weigh comfort (seat, lounge, legroom) against price,
    not just the cheapest.
  - If the traveller revises a constraint, replan around the new constraint.
""".strip(),
    description=(
        "Planner specialist (native ReAct) — flight search, budget/comfort "
        "tradeoffs, and region-wide fare search."
    ),
    tools=[search_flights, search_cheapest_in_region, compare_business_class],
)


# ── Support specialist — lite model, single lookups (no planner needed) ─────

support_specialist = LlmAgent(
    name="support_specialist",
    model=LiteLlm(model=LITE_MODEL),
    instruction="""
You are TravelBot's Support specialist. Handle two kinds of request:
  - Cancellation/change policy → get_cancellation_policy(booking_type)
  - Booking status lookups → get_booking_status(booking_id)

Rules:
  - These are single-lookup answers — call the relevant tool once and answer.
  - If asked about a booking with no reference, ask for one.
  - If a reference isn't found, say so plainly. Keep answers to 2-3 sentences.
""".strip(),
    description="Support specialist — cancellation policy and booking status lookups.",
    tools=[get_cancellation_policy, get_booking_status],
)


# ── Concierge router (lite model) ───────────────────────────────────────────

concierge_agent = LlmAgent(
    name="concierge_agent",
    model=LiteLlm(model=LITE_MODEL),
    instruction="""
You are TravelBot. Route every request to the right specialist. You have no
tools yourself.

Routing:
  - Flight search, price/comfort comparisons, budget tradeoffs → planner_specialist
  - Cancellation policy or booking status → support_specialist

If the request is outside travel booking and planning, say so plainly and ask
if there's a travel request you can help with instead. Do not transfer for
out-of-scope requests.
""".strip(),
    description="TravelBot concierge — routes to the Planner or Support specialist.",
    sub_agents=[planner_specialist, support_specialist],
)

root_agent = concierge_agent
