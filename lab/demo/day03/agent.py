"""
agent.py — Day 03 Travel Agent
================================
Defines the `aria` agent used by demo.py.

This module is intentionally minimal:
  - instruction  (what Aria knows and does)
  - tools        (get_flight_status, search_hotels from tools.py)
  - aria         (LlmAgent wiring the above together)

Session management lives in session.py.
Tool logic lives in tools.py.
"""

import logging
import os

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

# ── Silence noisy loggers ──────────────────────────────────────────────────
logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False

litellm.suppress_debug_info = True
load_dotenv()

from tools import get_flight_status, get_trip_summary, save_traveler_name, search_hotels

# ── Model ──────────────────────────────────────────────────────────────────
_MODEL = "openrouter/google/gemini-2.5-flash"

# ── Instruction ────────────────────────────────────────────────────────────
_INSTRUCTION = """
You are Aria, a professional travel assistant.

Your capabilities:
- Check flight status using the get_flight_status tool.
- Search for hotels in a city using the search_hotels tool.
- Save the traveler's name using save_traveler_name when they introduce themselves.
- Return a structured trip summary using get_trip_summary when asked.
- Help travelers plan and refine trip details across turns.

Guidelines:
- Always call the appropriate tool when the user asks about a flight or hotel.
  Do NOT guess or invent flight statuses or hotel listings.
- Call save_traveler_name as soon as the user shares their name.
- Call get_trip_summary when the user asks for a summary, recap, or
  "what do you know about my trip".
- Use the traveler's name in every reply once it is known.
- Remember destination and preferences stated earlier in the session.
- If asked about something outside travel (e.g. writing code), politely
  decline and offer to help with travel instead.
- Keep responses clear, warm, and concise.
""".strip()

# ── Agent ──────────────────────────────────────────────────────────────────
aria = LlmAgent(
    name="aria",
    model=LiteLlm(model=_MODEL),
    instruction=_INSTRUCTION,
    description=(
        "A travel assistant that checks flight status, searches hotels, "
        "and remembers traveler context across a multi-turn session."
    ),
    tools=[get_flight_status, search_hotels, save_traveler_name, get_trip_summary],
)
