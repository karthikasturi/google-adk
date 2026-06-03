"""
agent.py — TravelBot v2: Tools + Session Memory
=================================================
Concept: Module 2 — Tool Calling and In-Memory Session State

Aria gains two tools:
    get_flight_status(flight_number) — check a flight's status
    search_hotels(city)             — find available hotels

Session memory is in-memory (InMemorySessionService via shared/session.py).
To switch to persistent storage, edit ONLY shared/session.py.

Import and use:
    from v2.agent import aria
    runner, user_id, session_id = await make_runner(aria)

Try these prompts in sequence (one session):
    "I'm flying on AI-204. Can you check the status?"
    "My name is Priya. I need a hotel in Tokyo."
    "Find one near the station."   ← follow-up — tests session memory
"""

import sys
from pathlib import Path

import litellm
from dotenv import load_dotenv

litellm.suppress_debug_info = True
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.models import build_agent
from shared.tools import TOOLS

# ── Instruction ────────────────────────────────────────────────────────────
_INSTRUCTION = """
You are Aria, a professional travel assistant for TravelBot.

Your capabilities (v2):
- Check flight status using the get_flight_status tool.
- Search for hotels in a city using the search_hotels tool.
- Save the traveler's name using save_traveler_name when they introduce themselves.
- Return a structured trip summary using get_trip_summary when asked.

Guidelines:
- Always call the appropriate tool when the user asks about a flight or hotel.
  Do NOT guess or invent flight statuses or hotel listings.
- Call save_traveler_name as soon as the user shares their name.
- Call get_trip_summary when the user asks for a summary or recap.
- Use the traveler's name in every reply once it is known.
- Remember destination and preferences stated earlier in the session.
- If asked about something outside travel, politely decline and offer
  travel assistance instead.

This is TravelBot v2 — tools and in-memory session state are now active.
RAG knowledge base is added in v3.
""".strip()

# ── Agent ──────────────────────────────────────────────────────────────────
aria = build_agent(
    name="aria_v2",
    instruction=_INSTRUCTION,
    description="TravelBot v2 — flight status + hotel search + session memory",
    tools=TOOLS,
)
