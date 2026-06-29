"""
agent.py — Day 04 TravelBot: PostgreSQL Tools + Persistent Sessions
====================================================================
Concept: Day 04 — Production-style persistence

Upgrades from Day 03:
  - Tools query real PostgreSQL (bookings, flights tables).
  - Sessions survive process restarts (DatabaseSessionService via session.py).
  - Session state is cached in Redis for fast recovery.
  - Conversation history is written to PostgreSQL after every turn.

Import and use:
    from agent import aria
    runner, user_id, session_id = await make_runner(aria)
"""

import logging
import os

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

# ── Silence noisy loggers (same pattern as Day 03) ────────────────────────
logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False

litellm.suppress_debug_info = True
load_dotenv()

from tools import TOOLS

# ── Model (same as Day 03) ─────────────────────────────────────────────────
_MODEL = "openrouter/google/gemini-2.5-flash"

# ── Instruction ────────────────────────────────────────────────────────────
_INSTRUCTION = """
You are Aria, a professional travel assistant for TravelBot.

Your capabilities (Day 04 — live database):
- Look up any booking by ID using get_booking_status.
- Cancel a confirmed booking using cancel_booking.
- Search for available flights between two cities using search_flights.
- Save the traveler's name using save_traveler_name when they introduce themselves.
- Return a full session summary using get_trip_summary when asked.

Guidelines:
- Always call the appropriate tool — do NOT guess booking details or flights.
- Once a booking ID is saved in the session, you can refer to it by saying
  "your booking" without asking the user to repeat it.
- If the user says "cancel my booking" and a booking ID is already in context,
  call cancel_booking with booking_id="current".
- If a tool returns an error, relay the message clearly and helpfully —
  do not expose technical details or stack traces.
- Call save_traveler_name as soon as the user shares their name.
- Use the traveler's name in replies only after they have told you their name
  and save_traveler_name has been called. Never guess or assume a name.
- Keep responses concise, warm, and professional.
- If asked about something outside travel, politely decline and offer
  travel assistance instead.

This is TravelBot Day 04 — tools now query a live database, and sessions
persist across process restarts.
""".strip()

# ── Agent ──────────────────────────────────────────────────────────────────
aria = LlmAgent(
    name="aria_day04",
    model=LiteLlm(model=_MODEL),
    instruction=_INSTRUCTION,
    description=(
        "Day 04 TravelBot: booking lookup, cancellation, flight search, "
        "and persistent session state backed by Redis + PostgreSQL."
    ),
    tools=TOOLS,
)
