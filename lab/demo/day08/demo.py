"""
demo.py — Day 08: TravelBot with FastMCP Tool Servers
========================================================
Google ADK · MCP Tool Servers (FastMCP) · OpenRouter

Runs five scripted scenarios:
  1A  Booking status   — get_booking_status, asks for a missing reference
  2A  Booking + hotel  — get_booking_details then find_hotels, reusing
                         the destination from the first tool call
  3A  Hotel timeout    — find_hotels times out on a slow MCP server,
                         Aria falls back gracefully
  3B  Unknown booking  — get_booking_status for an ID that doesn't exist
  4A  Cancel safety    — cancel_booking only takes ONE booking_id; Aria
                         uses list_bookings instead of bulk-cancelling
  5A  Observability    — full trace of tool calls/results for a flow

Then drops into a REPL that prints the same tool-call trace for every
turn. Type  q  to quit.

Run:
    cp .env.example .env   # fill in OPENROUTER_API_KEY
    python demo.py         # all scenarios then REPL
    python demo.py --repl  # skip scenarios, go straight to REPL
"""

import asyncio
import logging
import os
import sys
import textwrap
import time

from dotenv import load_dotenv
from google.genai import types

load_dotenv()

# ── Silence noise (same as previous days) ──────────────────────────────────
logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False

from agent import (
    booking_toolset,
    hotel_toolset,
    root_agent,
    slow_hotel_toolset,
    timeout_demo_agent,
    timeout_demo_booking_toolset,
    _SLOW_HOTEL_DELAY_SECONDS,
    _SLOW_HOTEL_TIMEOUT_SECONDS,
)
from session import make_runner

# ── Scenario guide ───────────────────────────────────────────────────────────
_GUIDE = """
  SCENARIO GUIDE — Day 08: TravelBot with FastMCP Tool Servers
  ──────────────────────────────────────────────────────────────────────
  1A  Booking status   get_booking_status — single MCP tool, asks for a
                        booking reference / email if it's missing
  2A  Booking + hotel  get_booking_details then find_hotels — the second
                        tool call reuses the destination from the first
  3A  Hotel timeout    find_hotels times out on a slow MCP server ->
                        graceful fallback message, no hang
  3B  Unknown booking  get_booking_status for an ID that doesn't exist ->
                        structured 'not found', no hallucination
  4A  Cancel safety    cancel_booking only takes ONE booking_id -> Aria
                        uses list_bookings and asks which one to cancel
  5A  Observability    full trace of tool calls, args and results for a
                        booking + hotel flow
  ──────────────────────────────────────────────────────────────────────
"""

# ── Console helpers ──────────────────────────────────────────────────────────


def _wrap(text: str, width: int = 74) -> str:
    prefix = "    "
    return textwrap.fill(text, width=width, initial_indent=prefix, subsequent_indent=prefix)


def _sep(char: str = "─", width: int = 70) -> None:
    print(f"  {char * width}")


def _build_message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


def _format_tool_result(response: dict) -> str:
    """Render an MCP tool's function_response for console output."""
    if "error" in response:
        return f"ERROR: {response['error']}"
    content = response.get("content")
    if isinstance(content, list) and content and "text" in content[0]:
        text = " ".join(content[0]["text"].split())
    else:
        text = str(response)
    return textwrap.shorten(text, width=160, placeholder=" ...")


def _print_trace(trace: list[dict]) -> None:
    """Print a tool-call trace captured by _ask_with_trace()."""
    for step in trace:
        if step["type"] == "call":
            args = ", ".join(f"{k}={v!r}" for k, v in step["args"].items())
            print(f"  [tool call]   {step['tool']}({args})")
        else:
            print(f"  [tool result] {step['tool']} -> {_format_tool_result(step['response'])}")


# ── ADK ask helpers ───────────────────────────────────────────────────────────


async def _ask(runner, user_id: str, session_id: str, prompt: str) -> str:
    reply = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=_build_message(prompt),
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                reply = event.content.parts[0].text or ""
    return reply.strip()


async def _ask_with_trace(runner, user_id: str, session_id: str, prompt: str) -> tuple[str, list[dict]]:
    """
    Like _ask(), but also returns a trace of every MCP tool call and
    result seen along the way — which tool, what arguments, what came
    back. This is what Scenario 5A and the REPL use to show observability
    into the MCP layer.
    """
    reply = ""
    trace: list[dict] = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=_build_message(prompt),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "function_call", None):
                    fc = part.function_call
                    trace.append({"type": "call", "tool": fc.name, "args": dict(fc.args or {})})
                if getattr(part, "function_response", None):
                    fr = part.function_response
                    trace.append({"type": "result", "tool": fr.name, "response": fr.response or {}})

        if event.is_final_response():
            if event.content and event.content.parts:
                reply = event.content.parts[0].text or ""

    return reply.strip(), trace


async def _turn(runner, user_id: str, session_id: str, prompt: str) -> str:
    print(f"  You: {prompt}\n")
    reply = await _ask(runner, user_id, session_id, prompt)
    print("  [aria]")
    print(_wrap(reply))
    print()
    return reply


# ── Scripted scenarios ────────────────────────────────────────────────────────


async def scenario_1a_booking_status(runner, user_id, session_id) -> None:
    _sep()
    print("  Scenario 1A — Check booking status (single MCP tool)")
    _sep()
    print("\n  Tool: get_booking_status(booking_id) — booking MCP server\n")

    await _turn(
        runner, user_id, session_id,
        "Check the status of my booking for tomorrow's flight from Bengaluru to Delhi.",
    )
    await _turn(runner, user_id, session_id, "It's TB-2001.")

    await _turn(
        runner, user_id, session_id,
        "I booked a flight to Singapore last week. Can you confirm my current booking status?",
    )
    await _turn(runner, user_id, session_id, "My email is john@example.com.")

    print(
        "  Notice: Aria asked for a booking reference (or email) before\n"
        "  calling the booking tools, then summarised status and route in\n"
        "  plain language instead of dumping raw tool output.\n"
    )


async def scenario_2a_flight_and_hotel(runner, user_id, session_id) -> None:
    _sep()
    print("  Scenario 2A — Booking + hotel in one flow")
    _sep()
    print("\n  Tools: get_booking_details then find_hotels (booking + hotel MCP servers)\n")

    await _turn(
        runner, user_id, session_id,
        "I'm flying from Mumbai to Dubai next Friday. Can you confirm my "
        "booking and suggest a mid-range hotel close to the city center?",
    )
    await _turn(runner, user_id, session_id, "My booking reference is TB-2002.")

    print(
        "  Notice: Aria called get_booking_details(TB-2002) to confirm the\n"
        "  Mumbai -> Dubai flight, then reused 'Dubai' from that result as\n"
        "  the city for find_hotels — the destination wasn't asked for twice.\n"
    )


async def scenario_3a_hotel_timeout(runner, user_id, session_id) -> None:
    _sep()
    print("  Scenario 3A — find_hotels timeout -> graceful fallback")
    _sep()
    print(f"\n  Hotel server delay : HOTEL_SEARCH_DELAY_SECONDS={_SLOW_HOTEL_DELAY_SECONDS}s")
    print(f"  Toolset timeout    : {_SLOW_HOTEL_TIMEOUT_SECONDS}s (shorter than the delay)\n")

    prompt = "Find me three hotel options in Bangkok for this weekend, near Sukhumvit, under ₹7,000 per night."
    print(f"  You: {prompt}\n")

    start = time.monotonic()
    reply, trace = await _ask_with_trace(runner, user_id, session_id, prompt)
    elapsed = time.monotonic() - start

    _print_trace(trace)
    print(f"  [tool call]   find_hotels timed out after {elapsed:.1f}s\n")
    print("  [aria]")
    print(_wrap(reply))

    print(
        "\n  Notice: the trace shows find_hotels was called and then timed\n"
        "  out — ADK turned that timeout into a normal {'error': ...} tool\n"
        "  result instead of hanging, and Aria fell back to a plain-language\n"
        "  apology instead of inventing hotel listings.\n"
    )


async def scenario_3b_unknown_booking(runner, user_id, session_id) -> None:
    _sep()
    print("  Scenario 3B — Unknown booking ID -> structured 'not found'")
    _sep()
    print("\n  Tool: get_booking_status(booking_id) — booking MCP server\n")

    await _turn(
        runner, user_id, session_id,
        "Check the status of booking ABC-999-ZZZ for my flight from Kochi to London next month.",
    )

    print(
        "  Notice: get_booking_status returned {'found': False, ...} for an\n"
        "  ID that doesn't exist. Aria reported that plainly — no invented\n"
        "  status or flight details — and offered a next step.\n"
    )


async def scenario_4a_cancel_safety(runner, user_id, session_id) -> None:
    _sep()
    print("  Scenario 4A — Cancellation safety (no bulk cancel)")
    _sep()
    print("\n  Tools: list_bookings, cancel_booking — booking MCP server")
    print("  cancel_booking only ever accepts ONE booking_id; there is no")
    print("  'cancel all bookings' tool.\n")

    await _turn(
        runner, user_id, session_id,
        "Cancel all flights under email john@example.com for next week.",
    )

    print(
        "  Notice: there is no tool for bulk cancellation, so Aria couldn't\n"
        "  do it even if asked. She used list_bookings (read-only) to find\n"
        "  the candidates and asked which single booking to cancel, instead\n"
        "  of guessing or looping cancel_booking herself.\n"
    )


async def scenario_5a_observability(runner, user_id, session_id) -> None:
    _sep()
    print("  Scenario 5A — Observability: tracing MCP tool calls")
    _sep()
    print("\n  Same kind of flow as Scenario 2A, but this time we print every")
    print("  tool call and tool result exactly as the ADK runner reports it.\n")

    prompt = "Confirm booking TB-2001 and suggest a hotel in Delhi under ₹6,000 per night."
    print(f"  You: {prompt}\n")

    reply, trace = await _ask_with_trace(runner, user_id, session_id, prompt)
    _print_trace(trace)
    print("\n  [aria]")
    print(_wrap(reply))

    print(
        "\n  Notice: each MCP server exposes a small, well-scoped set of\n"
        "  tools — booking_server (status / details / list / cancel) and\n"
        "  hotel_server (find_hotels). The trace above is exactly what you'd\n"
        "  capture for observability in production: which tool ran, with\n"
        "  what arguments, what it returned, and how those results were\n"
        "  combined into the final answer.\n"
    )


# ── Free REPL ──────────────────────────────────────────────────────────────────


async def run_repl(runner, user_id, session_id) -> None:
    _sep("═")
    print("  Free REPL — Aria with booking + hotel MCP tools.")
    print("  Every tool call and result is traced. Type a prompt or  q  to quit.")
    _sep("═")

    while True:
        try:
            prompt = input("  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if prompt.lower() == "q":
            break
        if not prompt:
            continue

        reply, trace = await _ask_with_trace(runner, user_id, session_id, prompt)
        if trace:
            _print_trace(trace)
        print("  [aria]")
        print(_wrap(reply))
        print()

    print("  ── session ended ──\n")


# ── Main ─────────────────────────────────────────────────────────────────────


async def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "\n[ERROR] OPENROUTER_API_KEY is not set.\n"
            "  Copy .env.example → .env and fill in your key.\n"
        )
        return

    print("""
+======================================================================+
|   DAY 08 — TravelBot with FastMCP Tool Servers                      |
|   Google ADK · MCP Tool Servers (FastMCP) · OpenRouter              |
+======================================================================+""")
    print(_GUIDE)

    repl_only = "--repl" in sys.argv

    try:
        if not repl_only:
            try:
                await scenario_1a_booking_status(*await make_runner(root_agent))
                await scenario_2a_flight_and_hotel(*await make_runner(root_agent))
                await scenario_3a_hotel_timeout(*await make_runner(timeout_demo_agent))
                await scenario_3b_unknown_booking(*await make_runner(root_agent))
                await scenario_4a_cancel_safety(*await make_runner(root_agent))
                await scenario_5a_observability(*await make_runner(root_agent))
            except KeyboardInterrupt:
                print("\n  Scenarios interrupted.\n")

            cont = input("  Continue to free REPL? [y/N]: ").strip().lower()
            if cont != "y":
                return

        await run_repl(*await make_runner(root_agent))
    finally:
        for toolset in (booking_toolset, hotel_toolset, timeout_demo_booking_toolset, slow_hotel_toolset):
            await toolset.close()


if __name__ == "__main__":
    asyncio.run(main())
