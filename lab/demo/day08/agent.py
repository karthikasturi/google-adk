"""
agent.py — Day 08 TravelBot: MCP tool servers via FastMCP
============================================================
Concept: Agents call out to small, well-scoped tool servers over MCP
instead of having tool functions baked into the agent process.

Two MCP servers (mcp_servers/booking_server.py, mcp_servers/hotel_server.py)
are started as stdio subprocesses and exposed to the agent as toolsets:

  booking_toolset — get_booking_status, get_booking_details, list_bookings,
                     cancel_booking
  hotel_toolset   — find_hotels (normal speed)

root_agent combines both toolsets for scenarios 1A, 2A, 3B and 4A.

timeout_demo_agent (Scenario 3A) uses a second hotel toolset whose server
process is started with HOTEL_SEARCH_DELAY_SECONDS set higher than the
toolset's own MCP timeout, so the find_hotels call times out and ADK's
graceful MCP error handling returns {"error": ...} instead of hanging.

ADK Web:
    adk web .          ← discovers root_agent automatically
"""

import logging
import os
import sys
from pathlib import Path

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

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

_SERVERS_DIR = Path(__file__).parent / "mcp_servers"
_BOOKING_SERVER = str(_SERVERS_DIR / "booking_server.py")
_HOTEL_SERVER = str(_SERVERS_DIR / "hotel_server.py")

# Scenario 3A tuning — see .env.example
_SLOW_HOTEL_DELAY_SECONDS = os.getenv("HOTEL_SEARCH_DELAY_SECONDS", "8")
_SLOW_HOTEL_TIMEOUT_SECONDS = float(os.getenv("HOTEL_TOOL_TIMEOUT_SECONDS", "3"))


_PERSONA = """
You are Aria, TravelBot's travel assistant. You help travellers check
flight bookings, look up booking details, and find hotels near their
destination.

You have access to these tools, provided by MCP tool servers:

Booking tools:
  - get_booking_status(booking_id): quick status check for one booking
  - get_booking_details(booking_id): full details for one booking
    (route, dates, cabin class, status)
  - list_bookings(email): all bookings for a traveller's email address
  - cancel_booking(booking_id, confirm): cancel ONE booking

Hotel tools:
  - find_hotels(city, max_price_per_night_inr, near): search hotels by
    city, with optional price ceiling and area/landmark preference

General rules:
  - If you need a booking reference or email to look something up and the
    user hasn't given you one, ask for it before calling a tool. Never
    guess or invent a booking ID.
  - Tool results are structured data, not conversation text. Read them
    carefully and summarise the relevant parts in plain language - don't
    dump raw JSON at the user.
  - Never invent booking details, statuses, or hotel listings. Only report
    what the tools return.
  - If a tool result has "found": false, or contains an "error" field,
    explain plainly what happened (for example, the booking reference
    wasn't found, or the hotel search is temporarily unavailable) and
    suggest a next step (double-check the reference, try again shortly, or
    adjust the search). Don't pretend the call succeeded, and don't retry
    the same tool call again - report the issue instead.

Multi-step flows:
  - If a request involves both a booking and a hotel (for example, "confirm
    my flight and suggest a hotel"), first call a booking tool to confirm
    the flight details, then use the destination city from that result for
    find_hotels. Don't ask the user to repeat information your tools
    already gave you.

Cancellations (safety-critical):
  - cancel_booking only ever cancels ONE specific booking_id. There is no
    tool to cancel multiple bookings at once, on purpose.
  - If a user asks to cancel "all" bookings, every booking for an email, or
    every booking matching some criteria, do NOT try to loop over
    cancel_booking yourself. Instead call list_bookings to show the
    candidates and ask the user which single booking_id they want to
    cancel.
  - Before cancelling, always confirm the specific booking with the user.
    Call cancel_booking with confirm=False (or omitted) first to preview,
    then call it again with confirm=True only after the user explicitly
    agrees.
""".strip()


def _booking_toolset() -> McpToolset:
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=[_BOOKING_SERVER],
            ),
            timeout=10,
        ),
    )


def _hotel_toolset(*, delay_seconds: str, timeout: float) -> McpToolset:
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=[_HOTEL_SERVER],
                env={"HOTEL_SEARCH_DELAY_SECONDS": delay_seconds},
            ),
            timeout=timeout,
        ),
    )


# ── Main agent — booking + hotel tools at normal speed ─────────────────────
booking_toolset = _booking_toolset()
hotel_toolset = _hotel_toolset(delay_seconds="0", timeout=10)

root_agent = LlmAgent(
    name="aria",
    model=LiteLlm(model=_MODEL),
    instruction=_PERSONA,
    description="Aria — TravelBot assistant backed by booking and hotel MCP tool servers.",
    tools=[booking_toolset, hotel_toolset],
)


# ── Timeout-demo agent (Scenario 3A) ────────────────────────────────────────
# Its own toolset instances so the slow hotel server doesn't share a
# subprocess/session with the normal-speed one above.
timeout_demo_booking_toolset = _booking_toolset()
slow_hotel_toolset = _hotel_toolset(
    delay_seconds=_SLOW_HOTEL_DELAY_SECONDS,
    timeout=_SLOW_HOTEL_TIMEOUT_SECONDS,
)

timeout_demo_agent = LlmAgent(
    name="aria_timeout_demo",
    model=LiteLlm(model=_MODEL),
    instruction=_PERSONA,
    description="Aria with a slow hotel MCP server, for demonstrating tool-call timeout fallback.",
    tools=[timeout_demo_booking_toolset, slow_hotel_toolset],
)
