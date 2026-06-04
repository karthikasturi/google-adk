"""
agent.py — TravelBot v3: PostgreSQL Tools + Session Persistence
================================================================
Concept: Day 04 upgrade — Production-style persistence

Aria gains new tools backed by PostgreSQL:
    get_booking_status(booking_id) — look up a booking
    cancel_booking(booking_id)     — cancel a confirmed booking
    search_flights(origin, destination) — search available flights

Session storage: configurable via SESSION_BACKEND env var
    database (default) — PostgreSQL via asyncpg
    redis              — Redis only, no SQL
    memory             — InMemorySessionService (no persistence)

Session state is cached in Redis for fast recovery.
Conversation history is stored in PostgreSQL session_history table.

Import and use:
    from v3.agent import aria
    runner, user_id, session_id = await make_runner(aria)

Try these prompts in sequence (one session):
    "Check booking TB-1001 for me."
    "What's the passenger name?"        ← follow-up, no ID repeated
    "Find flights from Mumbai to London."
    "Cancel booking TB-1002."
"""

import os
import sys
from pathlib import Path

import litellm
from dotenv import load_dotenv

litellm.suppress_debug_info = True
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.models import build_agent
from shared.tools import TOOLS_V3

# ── Instruction ────────────────────────────────────────────────────────────
_INSTRUCTION = """
You are Aria, a professional travel assistant for TravelBot.

Your capabilities (v3 — production persistence):
- Look up any booking by ID using get_booking_status.
- Cancel a confirmed booking using cancel_booking.
- Search for available flights using search_flights.
- Check flight status using get_flight_status.
- Search for hotels using search_hotels.
- Save the traveler's name using save_traveler_name.
- Return a structured trip summary using get_trip_summary.

Guidelines:
- Always call the appropriate tool — do NOT guess booking details or flights.
  All data comes from a live PostgreSQL database.
- Once a booking ID is saved in the session, refer to it as "your booking"
  in follow-up questions without asking the user to repeat it.
- If the user says "cancel my booking" and a booking ID is in context,
  call cancel_booking with booking_id="current".
- If a tool returns an error, relay the message clearly and helpfully.
  Do not expose technical details or stack traces.
- Call save_traveler_name as soon as the user shares their name.
- Use the traveler's name in every reply once it is known.
- Keep responses concise, warm, and professional.
- If asked about something outside travel, politely decline and offer
  travel assistance instead.

This is TravelBot v3 — tools query a live database, and sessions
persist across process restarts via PostgreSQL or Redis.
""".strip()

# ── Agent ──────────────────────────────────────────────────────────────────
aria = build_agent(
    name="aria_v3",
    instruction=_INSTRUCTION,
    description=(
        "TravelBot v3 — booking lookup, cancellation, flight search, "
        "and persistent session state backed by PostgreSQL + optional Redis cache."
    ),
    tools=TOOLS_V3,
)
