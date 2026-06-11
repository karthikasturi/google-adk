"""
agent.py — Day 08 TravelBot: MCP tool servers via FastMCP
============================================================
Concept: Agents call out to small, well-scoped tool servers over MCP
instead of having tool functions baked into the agent process. This demo
deliberately mixes two MCP transports:

  booking_toolset — mcp_servers/booking_server.py, run ONCE as a
                     background Streamable HTTP server (its own process,
                     listening on http://127.0.0.1:8765/mcp). A single
                     McpToolset/HTTP client session is shared by both agents
                     below via StreamableHTTPConnectionParams.
                     Tools: get_booking_status, get_booking_details,
                     list_bookings, cancel_booking

  hotel_toolset   — mcp_servers/hotel_server.py, spawned per-toolset as a
                     stdio subprocess via StdioConnectionParams.
                     Tools: find_hotels (normal speed)

root_agent combines both toolsets for scenarios 1A, 2A, 3B and 4A.

timeout_demo_agent (Scenario 3A) uses a second hotel toolset whose server
process is started with HOTEL_SEARCH_DELAY_SECONDS set higher than the
toolset's own MCP timeout, so the find_hotels call times out and ADK's
graceful MCP error handling returns {"error": ...} instead of hanging.

ADK Web:
    adk web .          ← discovers root_agent automatically
"""

import atexit
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import (
    McpToolset,
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
)
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

# ── Booking server: Streamable HTTP, started once as a background process ──
_BOOKING_HOST = os.getenv("BOOKING_SERVER_HOST", "127.0.0.1")
_BOOKING_PORT = int(os.getenv("BOOKING_SERVER_PORT", "8765"))
_BOOKING_URL = f"http://{_BOOKING_HOST}:{_BOOKING_PORT}/mcp"


def _wait_for_port(host: str, port: int, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"booking_server.py did not start on {host}:{port} within {timeout}s")


def _start_booking_server() -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, _BOOKING_SERVER],
        env={**os.environ, "BOOKING_SERVER_HOST": _BOOKING_HOST, "BOOKING_SERVER_PORT": str(_BOOKING_PORT)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_for_port(_BOOKING_HOST, _BOOKING_PORT)
    return proc


_booking_server_process = _start_booking_server()


def shutdown_booking_server() -> None:
    """Stop the background booking MCP server. Safe to call more than once."""
    if _booking_server_process.poll() is None:
        _booking_server_process.terminate()
        _booking_server_process.wait(timeout=5)


atexit.register(shutdown_booking_server)


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
        connection_params=StreamableHTTPConnectionParams(
            url=_BOOKING_URL,
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
# Reuses the shared booking_toolset (one HTTP client session per process is
# enough — opening a second concurrent session against the same booking
# server here led to MCP session-setup errors). Only the hotel toolset
# differs: its own stdio subprocess, started with HOTEL_SEARCH_DELAY_SECONDS
# higher than its own MCP timeout so find_hotels times out.
slow_hotel_toolset = _hotel_toolset(
    delay_seconds=_SLOW_HOTEL_DELAY_SECONDS,
    timeout=_SLOW_HOTEL_TIMEOUT_SECONDS,
)

timeout_demo_agent = LlmAgent(
    name="aria_timeout_demo",
    model=LiteLlm(model=_MODEL),
    instruction=_PERSONA,
    description="Aria with a slow hotel MCP server, for demonstrating tool-call timeout fallback.",
    tools=[booking_toolset, slow_hotel_toolset],
)
