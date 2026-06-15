"""
agent.py — Day 09a: Native ADK multi-agent patterns
======================================================
Day 09 built multi-agent orchestration "by hand": a single Orchestrator
LlmAgent with custom *delegation tools* (delegate_to_trips_agent /
delegate_to_support_agent) that ran each specialist in its own
Runner+session and returned plain text to the Orchestrator.

Day 09a wires up the same TravelBot specialists using ADK's *built-in*
multi-agent building blocks instead - three small, independent demos:

  A. Agent routing (sub_agents + transfer_to_agent)
       concierge_agent
         +- trips_specialist    (get_attractions)
         +- support_agent       (get_booking_status)

     concierge_agent has no delegation tools at all. Because
     trips_specialist / support_specialist are its sub_agents, ADK
     automatically gives every agent in this tree a transfer_to_agent
     tool and the instructions for when to use it. A transfer hands the
     *whole turn* (and, for the rest of the session, the conversation)
     to the target agent - including peer-to-peer handoffs between the
     two specialists, with no need to go back through the concierge.

  B. Sequential workflow graph (Workflow + edges)
       trip_prep_pipeline = Workflow(edges=[
           (START, booking_check_step, itinerary_step, recap_step),
       ])

     A fixed pipeline graph that always runs in this order. Each step
     writes its result to session state via output_key, and the next
     step's instruction pulls it back in with {state_key} templating.

  C. Parallel + sequential workflow graph (fan-out, then fan-in)
       trip_research_join = JoinNode(name="trip_research_join")
       trip_research_pipeline = Workflow(edges=[
           (START, attractions_researcher, trip_research_join),
           (START, weather_researcher, trip_research_join),
           (trip_research_join, trip_synthesizer),
       ])

     Two independent specialists run *concurrently* from START
     (fan-out), each writing its findings to state. trip_research_join
     waits for both branches, then trip_synthesizer reads both and
     produces one weather-aware itinerary (fan-in).

  (SequentialAgent / ParallelAgent / LoopAgent are deprecated in this
  ADK version in favour of Workflow - a graph of edges starting at
  START, with JoinNode for fan-in.)

ADK Web:
    adk web .          ← discovers root_agent (concierge_agent, Pattern A)
"""

import logging
import os

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.workflow import JoinNode, START, Workflow

from tools import get_attractions, get_booking_status, get_weather_forecast

# ── Silence noisy loggers (same pattern as previous days) ─────────────────
logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False

litellm.suppress_debug_info = True
load_dotenv()

_MODEL = "openrouter/google/gemini-2.5-flash"


# ═══════════════════════════════════════════════════════════════════════════
# Pattern A — Agent routing via sub_agents + transfer_to_agent
# ═══════════════════════════════════════════════════════════════════════════

_TRIPS_PERSONA = """
You are TravelBot's Trips specialist, speaking directly with the
traveller. Help them plan itineraries and suggest activities using
get_attractions(city, days, interests).

Rules:
  - Use get_attractions before suggesting anything - don't invent
    attractions it didn't return.
  - When a number of days is given, group the attractions into a simple
    day-by-day plan. Keep it concise.
  - If get_attractions has no data for the city, say so plainly.
  - If the traveller then asks about something outside trip planning
    (for example, a booking), that's not your area - hand the
    conversation off to whichever agent covers it.
""".strip()

trips_specialist = LlmAgent(
    name="trips_specialist",
    model=LiteLlm(model=_MODEL),
    instruction=_TRIPS_PERSONA,
    description="Trips specialist - itinerary planning and activity suggestions for a destination.",
    tools=[get_attractions],
)


_SUPPORT_PERSONA = """
You are TravelBot's Support specialist, speaking directly with the
traveller. Help them check the status of a flight booking using
get_booking_status(booking_id, origin, destination).

Rules:
  - Look up by booking_id if the traveller gave one, otherwise by
    origin and/or destination.
  - Tool results are structured data, not conversation text. Summarise
    the relevant parts in plain language - don't dump raw JSON.
  - If the booking is delayed, report the new arrival time clearly.
  - If a result has "found": false or an "error" field, explain plainly
    what happened and suggest a next step - don't pretend it succeeded.
  - If the traveller then asks about planning or activities, that's not
    your area - hand the conversation off to whichever agent covers it.
""".strip()

support_specialist = LlmAgent(
    name="support_specialist",
    model=LiteLlm(model=_MODEL),
    instruction=_SUPPORT_PERSONA,
    description="Support specialist - flight booking status lookups.",
    tools=[get_booking_status],
)


_CONCIERGE_PERSONA = """
You are TravelBot's front-desk Concierge. Greet travellers and answer
general questions about what TravelBot can do.

You have no booking or itinerary tools yourself - if a request needs
one, hand it off to the specialist who covers it rather than guessing.
""".strip()

concierge_agent = LlmAgent(
    name="concierge_agent",
    model=LiteLlm(model=_MODEL),
    instruction=_CONCIERGE_PERSONA,
    description=(
        "TravelBot front desk - greets travellers and routes itinerary "
        "questions to the Trips specialist and booking questions to the "
        "Support specialist."
    ),
    sub_agents=[trips_specialist, support_specialist],
)


# ═══════════════════════════════════════════════════════════════════════════
# Pattern B — Workflow: a fixed pipeline graph (one path from START)
# ═══════════════════════════════════════════════════════════════════════════

_BOOKING_STEP_PERSONA = """
Step 1 of the trip-prep pipeline. Look up the traveller's booking with
get_booking_status(booking_id, origin, destination), using whatever
reference or route is in the request.

Write a short (1-2 sentence) summary of the booking status - if it's
delayed, include the new arrival time. If nothing matches, say so
plainly. This summary is read by the next step, not shown to the
traveller directly.
""".strip()

booking_check_step = LlmAgent(
    name="booking_check_step",
    model=LiteLlm(model=_MODEL),
    instruction=_BOOKING_STEP_PERSONA,
    description="Pipeline step 1 - looks up the traveller's booking status.",
    tools=[get_booking_status],
    output_key="booking_summary",
)


_ITINERARY_STEP_PERSONA = """
Step 2 of the trip-prep pipeline. Plan a day-by-day itinerary for the
traveller's request using get_attractions(city, days, interests).

Booking status from step 1:
{booking_summary}

If that summary mentions a delay or a changed arrival time, adjust the
itinerary accordingly (for example, trim or shift day 1's plans).
Otherwise plan normally. Keep it concise - a short list per day. This
plan is read by the next step, not shown to the traveller directly.
""".strip()

itinerary_step = LlmAgent(
    name="itinerary_step",
    model=LiteLlm(model=_MODEL),
    instruction=_ITINERARY_STEP_PERSONA,
    description="Pipeline step 2 - plans a day-by-day itinerary, adjusted for any delay from step 1.",
    tools=[get_attractions],
    output_key="itinerary_plan",
)


_RECAP_STEP_PERSONA = """
Step 3 of the trip-prep pipeline - the only step the traveller sees.
Combine the results below into one friendly recap, booking status
first and then the itinerary. Don't repeat yourself or add new
information - just combine what's given here.

Booking status:
{booking_summary}

Itinerary:
{itinerary_plan}
""".strip()

recap_step = LlmAgent(
    name="recap_step",
    model=LiteLlm(model=_MODEL),
    instruction=_RECAP_STEP_PERSONA,
    description="Pipeline step 3 - combines the booking status and itinerary into one recap for the traveller.",
    output_key="trip_recap",
)

trip_prep_pipeline = Workflow(
    name="trip_prep_pipeline",
    description=(
        "Trip-prep pipeline - checks a booking, plans an itinerary that "
        "accounts for any delay, then recaps both. Always runs in this "
        "fixed order."
    ),
    edges=[
        (START, booking_check_step, itinerary_step, recap_step),
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# Pattern C — Workflow: fan-out from START, JoinNode fan-in
# ═══════════════════════════════════════════════════════════════════════════

_ATTRACTIONS_RESEARCH_PERSONA = """
Research step (runs concurrently with weather research). Use
get_attractions(city, days, interests) for the destination in the
request and list what it returns, grouped by category. This is raw
research for a later step, not shown to the traveller directly.
""".strip()

attractions_researcher = LlmAgent(
    name="attractions_researcher",
    model=LiteLlm(model=_MODEL),
    instruction=_ATTRACTIONS_RESEARCH_PERSONA,
    description="Research step - lists attractions for the destination.",
    tools=[get_attractions],
    output_key="attractions_findings",
)


_WEATHER_RESEARCH_PERSONA = """
Research step (runs concurrently with attractions research). Use
get_weather_forecast(city, days) for the destination in the request and
summarise the forecast day by day. This is raw research for a later
step, not shown to the traveller directly.
""".strip()

weather_researcher = LlmAgent(
    name="weather_researcher",
    model=LiteLlm(model=_MODEL),
    instruction=_WEATHER_RESEARCH_PERSONA,
    description="Research step - summarises the weather forecast for the destination.",
    tools=[get_weather_forecast],
    output_key="weather_findings",
)


_SYNTHESIS_PERSONA = """
Final step - the only one the traveller sees. Combine the research
below into a day-by-day plan for the requested number of days.

Attractions found:
{attractions_findings}

Weather forecast:
{weather_findings}

Match activities to good-weather days where possible - for example,
move outdoor attractions away from rainy/stormy/sandstorm days and
toward sunny ones. Briefly mention *why* you ordered the days that way.
""".strip()

trip_synthesizer = LlmAgent(
    name="trip_synthesizer",
    model=LiteLlm(model=_MODEL),
    instruction=_SYNTHESIS_PERSONA,
    description="Final step - combines the attractions and weather research into one weather-aware day-by-day plan.",
    output_key="trip_recommendation",
)

trip_research_join = JoinNode(name="trip_research_join")

trip_research_pipeline = Workflow(
    name="trip_research_pipeline",
    description=(
        "Researches a destination's attractions and weather in parallel, "
        "then synthesizes both into one weather-aware itinerary."
    ),
    edges=[
        (START, attractions_researcher, trip_research_join),
        (START, weather_researcher, trip_research_join),
        (trip_research_join, trip_synthesizer),
    ],
)


# ── adk web entry point ─────────────────────────────────────────────────────
root_agent = concierge_agent
