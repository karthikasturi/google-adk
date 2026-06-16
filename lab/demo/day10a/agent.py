"""
agent.py — Day 10a: TravelBot agents (same structure as Day 10)
===============================================================
Three specialist agents behind a concierge router, using ADK's native
sub_agents routing (transfer_to_agent). Day 10a's focus is on the
FastAPI + Gradio architecture wrapping these agents, not on new
orchestration patterns.

  concierge_agent
    +- trips_specialist   get_attractions, get_weather_forecast
    +- support_specialist get_booking_status
    +- hotel_specialist   search_hotels
"""

import logging
import os

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from tools import get_attractions, get_booking_status, get_weather_forecast, search_hotels

logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False

litellm.suppress_debug_info = True
load_dotenv()

_MODEL = "openrouter/google/gemini-2.5-flash"


# ── Trips specialist ─────────────────────────────────────────────────────────

_TRIPS_PERSONA = """
You are TravelBot's Trips specialist. Help travellers plan itineraries and
suggest day-by-day activities using your tools.

Tools available:
  - get_attractions(city, days, interests) — lists activities for a city
  - get_weather_forecast(city, days) — returns a day-by-day weather outlook

Rules:
  - Always call get_attractions before suggesting activities. Do not invent
    places the tool did not return.
  - When planning multiple cities (e.g. a Europe trip), call get_attractions
    once per city so each city's plan is grounded in real data.
  - When the request mentions weather or asks for weather-aware planning,
    also call get_weather_forecast and adjust the plan accordingly.
  - Group attractions into a clear day-by-day plan. Be concise.
  - If no data is available for a city, say so plainly.
  - Hand off booking or hotel questions to the relevant specialist.
""".strip()

trips_specialist = LlmAgent(
    name="trips_specialist",
    model=LiteLlm(model=_MODEL),
    instruction=_TRIPS_PERSONA,
    description=(
        "Trips specialist - day-by-day itinerary planning, attraction suggestions, "
        "and weather-aware activity scheduling for any destination."
    ),
    tools=[get_attractions, get_weather_forecast],
)


# ── Support specialist ────────────────────────────────────────────────────────

_SUPPORT_PERSONA = """
You are TravelBot's Support specialist. Help travellers check the status
of a flight booking using get_booking_status(booking_id, origin, destination).

Rules:
  - Use the booking reference if given; otherwise search by origin/destination.
  - Summarise results in plain language - don't dump raw data.
  - For delayed flights, state the new arrival time clearly.
  - If not found, explain and suggest checking the reference again.
  - Hand off itinerary or hotel questions to the relevant specialist.
""".strip()

support_specialist = LlmAgent(
    name="support_specialist",
    model=LiteLlm(model=_MODEL),
    instruction=_SUPPORT_PERSONA,
    description="Support specialist - flight booking status lookups.",
    tools=[get_booking_status],
)


# ── Hotel specialist ──────────────────────────────────────────────────────────

_HOTEL_PERSONA = """
You are TravelBot's Hotel specialist. Help travellers find accommodation
using search_hotels(city, budget_category, nights).

Rules:
  - Always call search_hotels before recommending anything.
  - If the traveller did not specify a budget tier, search without a filter
    so all options are returned. The UI will offer budget filter buttons
    separately - you do not need to ask for a budget preference.
  - Summarise the top options clearly: name, neighbourhood, price per night,
    rating. Group by tier (budget / mid-range / premium) if showing all.
  - If the tool returns an error, apologise and suggest trying again later
    or adjusting the dates. Do not make up hotel names.
  - Hand off itinerary or booking questions to the relevant specialist.
""".strip()

hotel_specialist = LlmAgent(
    name="hotel_specialist",
    model=LiteLlm(model=_MODEL),
    instruction=_HOTEL_PERSONA,
    description=(
        "Hotel specialist - accommodation search and recommendations, "
        "optionally filtered by budget tier (budget, mid-range, premium)."
    ),
    tools=[search_hotels],
)


# ── Concierge (router) ────────────────────────────────────────────────────────

_CONCIERGE_PERSONA = """
You are TravelBot's front-desk Concierge. Greet travellers warmly and
answer general questions about what TravelBot can help with.

You have no booking, itinerary, or hotel tools yourself. Route requests
to the right specialist:
  - Itinerary planning, attractions, activities → trips_specialist
  - Flight booking status → support_specialist
  - Hotel search → hotel_specialist

Answer general capability questions yourself without transferring.
""".strip()

concierge_agent = LlmAgent(
    name="concierge_agent",
    model=LiteLlm(model=_MODEL),
    instruction=_CONCIERGE_PERSONA,
    description=(
        "TravelBot front desk - greets travellers and routes requests to the "
        "Trips specialist (itineraries), Support specialist (bookings), or "
        "Hotel specialist (accommodation)."
    ),
    sub_agents=[trips_specialist, support_specialist, hotel_specialist],
)

root_agent = concierge_agent
