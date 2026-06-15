"""
agent.py — Day 09 TravelBot: multi-agent orchestration
==========================================================
Concept: a single root "Orchestrator" agent routes each request to one of
two small, well-scoped specialists - or answers the request directly
itself.

  trips_agent   — itinerary planning / activity suggestions
                   (tools.get_attractions)
  support_agent — flight booking status lookups
                   (tools.get_booking_status)

The Orchestrator never calls get_attractions/get_booking_status directly.
Instead it calls a *delegation tool* per specialist
(delegate_to_trips_agent / delegate_to_support_agent). Each delegation tool
runs the specialist agent in its own Runner + session and returns the
specialist's reply as plain text to the Orchestrator's LLM. This is the
"Planner-Executor" pattern: the Orchestrator (Planner) decides which
specialist(s) (Executors) to invoke, in what order, and how to combine
their results - all within a single turn if needed.

For Scenario 5A (Support specialist backend error), support_agent_error and
orchestrator_error_demo wire up the same delegation pattern but point at
get_booking_status_unavailable, which always returns {"error": ...} - this
shows how the Orchestrator reports a specialist failure without crashing or
retrying forever.

ADK Web:
    adk web .          ← discovers root_agent automatically
"""

import logging
import os

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

from session import make_runner
from tools import get_attractions, get_booking_status, get_booking_status_unavailable

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


# ── Specialist: Trips ───────────────────────────────────────────────────────
_TRIPS_PERSONA = """
You are TravelBot's Trips specialist. You help travellers plan itineraries
and suggest activities for a destination, using
get_attractions(city, days, interests).

Rules:
  - Use get_attractions to find real activities before suggesting anything.
    Don't invent attractions it didn't return.
  - If the request mentions a schedule change (for example, a delayed
    flight and a new arrival time), take that into account - say which
    day's plans might need to shift or be trimmed as a result.
  - When a number of days is given, group the attractions into a simple
    day-by-day plan. Keep it concise - a short list per day is enough.
  - If get_attractions returns no data for the city, say so plainly and
    don't invent a plan.
""".strip()

trips_agent = LlmAgent(
    name="trips_agent",
    model=LiteLlm(model=_MODEL),
    instruction=_TRIPS_PERSONA,
    description="Trips specialist - itinerary planning and activity suggestions.",
    tools=[get_attractions],
)


# ── Specialist: Support ─────────────────────────────────────────────────────
_SUPPORT_PERSONA = """
You are TravelBot's Support specialist. You help travellers check the
status of their flight bookings, using
get_booking_status(booking_id, origin, destination).

Rules:
  - If the traveller gave a booking reference, look up by booking_id.
    Otherwise, pass the origin and/or destination they described.
  - Tool results are structured data, not conversation text. Summarise the
    relevant parts in plain language - don't dump raw JSON.
  - If the booking is delayed, report the new arrival time clearly - other
    parts of the trip may depend on it.
  - If a tool result has "found": false, or contains an "error" field,
    explain plainly what happened and suggest a next step (double-check
    the reference, or try again shortly). Don't pretend the call
    succeeded, and don't retry the same tool call again.
  - Never invent booking details or statuses. Only report what the tool
    returns.
""".strip()

support_agent = LlmAgent(
    name="support_agent",
    model=LiteLlm(model=_MODEL),
    instruction=_SUPPORT_PERSONA,
    description="Support specialist - flight booking status lookups.",
    tools=[get_booking_status],
)

# Scenario 5A only: same persona, but its tool always reports a backend
# outage - see delegate_to_support_agent_error / orchestrator_error_demo.
support_agent_error = LlmAgent(
    name="support_agent",
    model=LiteLlm(model=_MODEL),
    instruction=_SUPPORT_PERSONA,
    description="Support specialist - flight booking status lookups.",
    tools=[get_booking_status_unavailable],
)


# ── Delegation tools + tracing ──────────────────────────────────────────────

# Populated by _run_specialist() while a delegation tool runs, and drained
# by demo.py after each top-level turn. Lets the demo print the specialist's
# own tool calls/results alongside the Orchestrator's trace.
delegation_trace: list[dict] = []


async def _run_specialist(agent: LlmAgent, request: str) -> str:
    """Run a specialist agent on `request` in its own runner/session.

    Records the specialist's tool calls/results into delegation_trace
    (tagged with the specialist's name), then returns its final reply text
    - this is what the Orchestrator's LLM sees as the tool result.
    """
    runner, user_id, session_id = await make_runner(agent)
    reply = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=request)]),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "function_call", None):
                    fc = part.function_call
                    delegation_trace.append(
                        {"agent": agent.name, "type": "call", "tool": fc.name, "args": dict(fc.args or {})}
                    )
                if getattr(part, "function_response", None):
                    fr = part.function_response
                    delegation_trace.append(
                        {"agent": agent.name, "type": "result", "tool": fr.name, "response": fr.response or {}}
                    )
        if event.is_final_response():
            if event.content and event.content.parts:
                reply = event.content.parts[0].text or ""
    return reply.strip()


async def delegate_to_trips_agent(request: str) -> str:
    """Ask the Trips specialist to plan or adjust an itinerary.

    Args:
        request: A self-contained description of what the traveller needs -
            destination, number of days, interests, and any relevant
            context from earlier in the conversation (for example, a
            schedule change reported by the Support specialist).

    Returns:
        The Trips specialist's reply, in plain language.
    """
    return await _run_specialist(trips_agent, request)


async def delegate_to_support_agent(request: str) -> str:
    """Ask the Support specialist to check a booking's status.

    Args:
        request: A self-contained description of what to look up - a
            booking reference if the traveller gave one, otherwise the
            route and/or travel day they described.

    Returns:
        The Support specialist's reply, in plain language.
    """
    return await _run_specialist(support_agent, request)


async def delegate_to_support_agent_error(request: str) -> str:
    """Ask the Support specialist to check a booking's status.

    Same as delegate_to_support_agent, but the booking backend is
    simulating an outage - used only by orchestrator_error_demo (Scenario
    5A) to demonstrate how the Orchestrator handles a specialist that
    reports an error.

    Args:
        request: A self-contained description of what to look up.

    Returns:
        The Support specialist's reply, in plain language (reporting the
        backend error).
    """
    return await _run_specialist(support_agent_error, request)


# ── Orchestrator ─────────────────────────────────────────────────────────────
_ORCHESTRATOR_PERSONA = """
You are TravelBot's Orchestrator. You don't look up bookings or plan
itineraries yourself - instead you coordinate two specialists:

  - A Trips specialist, for itinerary planning, activity suggestions, and
    adjusting existing plans.
  - A Support specialist, for flight booking status and confirmations.

Routing rules:
  - If the request is only about planning, activities, or adjusting an
    itinerary, delegate to the Trips specialist.
  - If the request is only about an existing booking's status, delegate to
    the Support specialist.
  - If a request needs BOTH (for example, "check my booking and also adjust
    my itinerary"), delegate to the Support specialist first, then to the
    Trips specialist - pass along anything relevant the Support specialist
    found (such as a new arrival time) so the itinerary suggestion can
    account for it. Then combine both results into one reply: booking
    status first, then the (possibly adjusted) plan.
  - If the request is a general question about what you can help with, or
    anything else that doesn't need a booking lookup or itinerary plan,
    answer directly yourself - don't delegate.

Delegation:
  - Each specialist only sees the request you send it, not the rest of the
    conversation - make each request self-contained (booking references,
    destinations, day counts, interests, etc. as relevant).
  - If a specialist's reply reports an error or an unavailable service, do
    not call it again for this turn. Pass that information to the user in
    plain language and suggest trying again later. Still complete any OTHER
    part of the request you can (for example, still delegate to the Trips
    specialist if only the Support specialist failed).
  - Never invent booking details or itinerary suggestions yourself - only
    use what the specialists return.
""".strip()

root_agent = LlmAgent(
    name="orchestrator",
    model=LiteLlm(model=_MODEL),
    instruction=_ORCHESTRATOR_PERSONA,
    description="TravelBot Orchestrator - routes requests to Trips/Support specialists or answers directly.",
    tools=[delegate_to_trips_agent, delegate_to_support_agent],
)


# ── Error-recovery demo (Scenario 5A) ───────────────────────────────────────
orchestrator_error_demo = LlmAgent(
    name="orchestrator_error_demo",
    model=LiteLlm(model=_MODEL),
    instruction=_ORCHESTRATOR_PERSONA,
    description="Orchestrator wired to a Support specialist whose backend is down, for error-recovery demos.",
    tools=[delegate_to_trips_agent, delegate_to_support_agent_error],
)
