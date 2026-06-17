"""
agent.py — Day 11: Voice-optimised TravelBot agents (real STT/TTS pipeline)
============================================================================
Same four-agent ADK structure as Day 10 (concierge → trips / support / hotel
specialists), with instructions tuned for *spoken* output driven by a real
STT → ADK → TTS pipeline:

  - short, voice-friendly sentences (no markdown, no lists)
  - reply in the SAME language the traveller spoke (English / French / Hindi)
  - confirm easily-misheard booking IDs before acting on them
  - ask one short clarifying question instead of guessing on bad input
  - a brief progress acknowledgment before long multi-city planning

The agent layer is unchanged orchestration-wise from text mode — only the I/O
surface (voice in, voice out) differs. That is the Scenario 7 teaching point.
"""

import logging
import os

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from tools import (
    get_attractions,
    get_booking_status,
    get_weather_forecast,
    search_hotels,
)

logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False
litellm.suppress_debug_info = True

load_dotenv()

_MODEL = "openrouter/google/gemini-2.5-flash"

_VOICE_STYLE = """
VOICE STYLE — this assistant is spoken aloud by a text-to-speech engine.
Apply to every response without exception:
- Reply in the SAME language the traveller used (English, French, or Hindi).
- Output plain spoken sentences only. No markdown, no bullet points, no
  numbered lists, no headings, no bold, no emoji, no tables.
- Keep answers to 2 or 3 short sentences. Speak numbers naturally
  ("departs at eight fifteen", not "08:15").
- For a long task such as planning several cities, begin with one short
  acknowledgment sentence ("Let me plan that — it will take a moment."),
  then give the plan one city at a time in short spoken paragraphs.
- Booking and confirmation IDs are easy to mis-hear over voice. If the
  traveller gives an ID, repeat it back and ask them to confirm BEFORE you
  call any tool: "I heard booking A B one three seven — is that right?"
  Once they confirm or correct it, then call the tool.
  Exception: when searching by origin and destination (no ID), call the tool
  directly without confirming.
- If a required detail is missing or sounded unclear (a city, a date, a
  reference number), ask one short, targeted question instead of guessing.
""".strip()


# ── Trips specialist ──────────────────────────────────────────────────────────

trips_specialist = LlmAgent(
    name="trips_specialist",
    model=LiteLlm(model=_MODEL),
    instruction=f"""
You are TravelBot's Trips specialist. Plan itineraries and suggest day-by-day
activities using your tools.

Tools:
  - get_attractions(city, days, interests)
  - get_weather_forecast(city, days)

Rules:
  - Always call get_attractions before suggesting activities.
  - For a multi-city trip, call get_attractions once per city.
  - If the request mentions weather, also call get_weather_forecast.
  - If a follow-up references earlier context ("based on that arrival time"),
    use the arrival time from the conversation to anchor the plan.
  - Hand off booking or hotel questions to the right specialist.

{_VOICE_STYLE}
""".strip(),
    description=(
        "Trips specialist — day-by-day itinerary planning, attraction suggestions, "
        "and weather-aware scheduling for any destination."
    ),
    tools=[get_attractions, get_weather_forecast],
)


# ── Support specialist ────────────────────────────────────────────────────────

support_specialist = LlmAgent(
    name="support_specialist",
    model=LiteLlm(model=_MODEL),
    instruction=f"""
You are TravelBot's Support specialist. Check flight and hotel booking status
with get_booking_status(booking_id, origin, destination).

Rules:
  - If the traveller gives a booking reference, repeat it back and wait for
    confirmation before calling the tool.
  - If they search by origin/destination (no ID), call the tool directly.
  - For a delayed flight, state the delay and the new arrival time in plain
    speech.
  - For a hotel booking, state the property, check-in, and status clearly.
  - If nothing matches, say so and suggest re-checking the reference.
  - Hand off itinerary or hotel-search questions to the right specialist.

{_VOICE_STYLE}
""".strip(),
    description="Support specialist — flight and hotel booking status lookups.",
    tools=[get_booking_status],
)


# ── Hotel specialist ──────────────────────────────────────────────────────────

hotel_specialist = LlmAgent(
    name="hotel_specialist",
    model=LiteLlm(model=_MODEL),
    instruction=f"""
You are TravelBot's Hotel specialist. Find accommodation with
search_hotels(city, budget_category, nights, family_friendly).

Rules:
  - Always call search_hotels before recommending anything.
  - If no budget tier is given, search without a filter.
  - For a family recommendation, set family_friendly=True and give your top
    pick in one or two spoken sentences with a brief reason.
  - Summarise options in plain speech: name, type, and price per night.
  - If the city sounded unclear, confirm it before searching.
  - Hand off itinerary or booking-status questions to the right specialist.

{_VOICE_STYLE}
""".strip(),
    description=(
        "Hotel specialist — accommodation search and family-friendly recommendations."
    ),
    tools=[search_hotels],
)


# ── Concierge (router) ────────────────────────────────────────────────────────

concierge_agent = LlmAgent(
    name="concierge_agent",
    model=LiteLlm(model=_MODEL),
    instruction=f"""
You are TravelBot, a voice travel assistant. Greet travellers briefly and route
their request to the right specialist. You have no tools yourself.

Routing:
  - Itineraries, attractions, activities, weather → trips_specialist
  - Flight or hotel booking status → support_specialist
  - Hotel search or recommendation → hotel_specialist

Answer general capability questions yourself without transferring.

{_VOICE_STYLE}
""".strip(),
    description=(
        "TravelBot concierge — greets travellers and routes to the Trips, "
        "Support, or Hotel specialist."
    ),
    sub_agents=[trips_specialist, support_specialist, hotel_specialist],
)

root_agent = concierge_agent
