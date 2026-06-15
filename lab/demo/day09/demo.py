"""
demo.py — Day 09: TravelBot Multi-Agent Orchestration
========================================================
Google ADK · Orchestrator + Trips/Support specialists · OpenRouter

Runs six scripted scenario groups:
  1A  Trips routing    — a planning-only request goes to the Trips
                         specialist only
  1B  Support routing  — a booking-status request goes to the Support
                         specialist only
  2A  Mixed intent      — one request needs both specialists; the
                         Orchestrator runs Support then Trips and combines
                         their replies (Planner-Executor)
  3A  Handoff           — turn 1 stays with Support, turn 2 hands off to
                         Trips, reusing context from turn 1
  4A  Direct answer     — a meta question is answered by the Orchestrator
                         itself, no delegation
  5A  Error recovery    — the Support specialist's backend is down; the
                         Orchestrator reports the issue gracefully

Then drops into a REPL that prints the same delegation trace for every
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

from agent import delegation_trace, orchestrator_error_demo, root_agent
from session import make_runner

# ── Scenario guide ───────────────────────────────────────────────────────────
_GUIDE = """
  SCENARIO GUIDE — Day 09: TravelBot Multi-Agent Orchestration
  ──────────────────────────────────────────────────────────────────────
  Orchestrator + two specialists:
    trips_agent    → itinerary planning, activities  (get_attractions)
    support_agent  → booking status lookups          (get_booking_status)
  ──────────────────────────────────────────────────────────────────────
  1A  Trips routing    a planning-only request -> Trips specialist only
  1B  Support routing  a booking-status request -> Support specialist only
  2A  Mixed intent     one request needs both -> Support then Trips,
                       combined into one reply (Planner-Executor)
  3A  Handoff          turn 1 stays with Support, turn 2 hands off to
                       Trips, reusing context from turn 1
  4A  Direct answer    a meta question -> Orchestrator answers itself,
                       no delegation
  5A  Error recovery   Support specialist's backend is down -> Orchestrator
                       reports the issue gracefully, no retry loop
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
    """Render a function_response dict for console output."""
    if "error" in response:
        return f"ERROR: {response['error']}"
    if "result" in response and isinstance(response["result"], str):
        text = " ".join(response["result"].split())
    else:
        text = str(response)
    return textwrap.shorten(text, width=160, placeholder=" ...")


def _print_trace(trace: list[dict], sub_trace: list[dict]) -> None:
    """Print the Orchestrator's delegation trace and, nested under it, each
    specialist's own tool calls/results captured in sub_trace."""
    if not trace and not sub_trace:
        print("  (no delegation — the Orchestrator answered directly)")
        return

    for step in trace:
        if step["type"] == "call":
            args = ", ".join(f"{k}={v!r}" for k, v in step["args"].items())
            print(f"  [orchestrator -> {step['tool']}]  call({args})")
        else:
            print(f"  [{step['tool']} -> orchestrator]  {_format_tool_result(step['response'])}")

    if sub_trace:
        print("\n  Inside the specialist(s):")
        for step in sub_trace:
            if step["type"] == "call":
                args = ", ".join(f"{k}={v!r}" for k, v in step["args"].items())
                print(f"    [{step['agent']}] tool call   {step['tool']}({args})")
            else:
                print(f"    [{step['agent']}] tool result {step['tool']} -> {_format_tool_result(step['response'])}")


# ── ADK ask helpers ───────────────────────────────────────────────────────────


async def _ask_with_trace(runner, user_id: str, session_id: str, prompt: str) -> tuple[str, list[dict], list[dict]]:
    """
    Run one turn and return (reply, trace, sub_trace):
      trace      — the Orchestrator's own delegate_to_* calls/results
      sub_trace  — each specialist's tool calls/results, captured via
                   agent.delegation_trace while the delegation tools ran
    """
    delegation_trace.clear()
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

    return reply.strip(), trace, list(delegation_trace)


async def _turn(runner, user_id: str, session_id: str, prompt: str) -> tuple[str, list[dict], list[dict]]:
    print(f"  You: {prompt}\n")
    reply, trace, sub_trace = await _ask_with_trace(runner, user_id, session_id, prompt)
    _print_trace(trace, sub_trace)
    print("\n  [orchestrator]")
    print(_wrap(reply))
    print()
    return reply, trace, sub_trace


# ── Scripted scenarios ────────────────────────────────────────────────────────


async def scenario_1a_trips_routing(runner, user_id, session_id) -> None:
    _sep()
    print("  Scenario 1A — Trips routing (single specialist)")
    _sep()
    print("\n  Expect: Orchestrator delegates to the Trips specialist only.\n")

    await _turn(
        runner, user_id, session_id,
        "Plan a 5-day family trip to Singapore in July with kid-friendly "
        "activities and one day at Sentosa.",
    )

    print(
        "  Notice: only delegate_to_trips_agent ran - no booking lookup was\n"
        "  needed for a pure planning request, and the Support specialist\n"
        "  was never involved.\n"
    )


async def scenario_1b_support_routing(runner, user_id, session_id) -> None:
    _sep()
    print("  Scenario 1B — Support routing (single specialist)")
    _sep()
    print("\n  Expect: Orchestrator delegates to the Support specialist only.\n")

    await _turn(
        runner, user_id, session_id,
        "Where is my booking for tomorrow's flight from Bengaluru to Delhi? "
        "The reference is BLR-DEL-123.",
    )

    print(
        "  Notice: only delegate_to_support_agent ran. get_booking_status was\n"
        "  called by the Support specialist, not by the Orchestrator directly\n"
        "  - the Orchestrator only ever sees the specialist's plain-language\n"
        "  reply.\n"
    )


async def scenario_2a_mixed_intent(runner, user_id, session_id) -> None:
    _sep()
    print("  Scenario 2A — Mixed intent (Planner-Executor)")
    _sep()
    print("\n  Expect: Support specialist runs first, then Trips - combined\n  into one reply.\n")

    await _turn(
        runner, user_id, session_id,
        "My Monday flight from Mumbai to Dubai was delayed; can you check "
        "my booking and also suggest how to adjust my 3-day Dubai "
        "itinerary?",
    )

    print(
        "  Notice: the trace shows delegate_to_support_agent ran before\n"
        "  delegate_to_trips_agent. The Support specialist reported the new\n"
        "  arrival time, and the Orchestrator passed that along so the Trips\n"
        "  specialist's itinerary accounts for the delay.\n"
    )


async def scenario_3a_handoff(runner, user_id, session_id) -> None:
    _sep()
    print("  Scenario 3A — Handoff within one conversation")
    _sep()
    print("\n  Turn 1: Support only. Turn 2: hands off to Trips, reusing\n  context from turn 1.\n")

    await _turn(
        runner, user_id, session_id,
        "Check the status of my flight from Chennai to Paris next week, "
        "reference CHN-PAR-789.",
    )
    await _turn(
        runner, user_id, session_id,
        "Great, now that it's confirmed, can you suggest how to spend 2 "
        "days in Paris with a focus on museums?",
    )

    print(
        "  Notice: turn 1 only used delegate_to_support_agent. Turn 2 only\n"
        "  used delegate_to_trips_agent - the Orchestrator didn't re-check\n"
        "  the booking, and the Trips specialist planned for Paris without\n"
        "  being told the destination again.\n"
    )


async def scenario_4a_direct_answer(runner, user_id, session_id) -> None:
    _sep()
    print("  Scenario 4A — Orchestrator answers directly")
    _sep()
    print("\n  Expect: no delegation at all for a meta/capabilities question.\n")

    await _turn(
        runner, user_id, session_id,
        "What kinds of things can you help me with as a travel assistant?",
    )

    print(
        "  Notice: the trace is empty - neither specialist was activated.\n"
        "  The Orchestrator described its own capabilities without calling\n"
        "  a tool.\n"
    )


async def scenario_5a_error_recovery(runner, user_id, session_id) -> None:
    _sep()
    print("  Scenario 5A — Error in a specialist, Orchestrator recovers")
    _sep()
    print("\n  This Orchestrator's Support specialist has a backend that\n  always reports an error.\n")

    await _turn(
        runner, user_id, session_id,
        "Check the status of my booking for flight BLR-LHR-456 next "
        "Friday.",
    )

    print(
        "  Notice: get_booking_status_unavailable returned {'error': ...}.\n"
        "  The Support specialist reported that plainly instead of\n"
        "  pretending to find a booking, delegate_to_support_agent returned\n"
        "  that report to the Orchestrator, and the Orchestrator passed it on\n"
        "  to the user with a suggestion to try again later - no retry loop,\n"
        "  no raw error dumped on the user.\n"
    )


def print_observability_notes() -> None:
    _sep("═")
    print("  Group 6 — Observability walkthrough")
    _sep("═")
    print(
        "\n  Use the traces above to discuss with the class:\n"
        "    - Which agent (orchestrator / trips_agent / support_agent)\n"
        "      produced each part of the answer?\n"
        "    - Where did the Orchestrator delegate ([orchestrator ->\n"
        "      delegate_to_*]), and when did it keep control (4A: empty\n"
        "      trace, answered directly)?\n"
        "    - 2A is Planner-Executor: one request, two delegations in\n"
        "      sequence, combined into one reply.\n"
        "    - 3A is a handoff: turn 1's specialist differs from turn 2's,\n"
        "      and turn 2 reuses turn 1's context instead of repeating work.\n"
        "    - 5A is the failure boundary: a specialist's tool returns\n"
        "      {'error': ...}, the specialist reports it in plain language,\n"
        "      and the Orchestrator relays it without retrying or crashing.\n"
        "\n  Each agent here is a small, well-scoped capability - the\n"
        "  Orchestrator's job is routing and combining, not doing the work\n"
        "  itself.\n"
    )


# ── Free REPL ──────────────────────────────────────────────────────────────────


async def run_repl(runner, user_id, session_id) -> None:
    _sep("═")
    print("  Free REPL — TravelBot Orchestrator with Trips + Support specialists.")
    print("  Every delegation is traced. Type a prompt or  q  to quit.")
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

        reply, trace, sub_trace = await _ask_with_trace(runner, user_id, session_id, prompt)
        _print_trace(trace, sub_trace)
        print("\n  [orchestrator]")
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
|   DAY 09 — TravelBot Multi-Agent Orchestration                       |
|   Google ADK · Orchestrator + Trips/Support specialists · OpenRouter |
+======================================================================+""")
    print(_GUIDE)

    repl_only = "--repl" in sys.argv

    if not repl_only:
        try:
            await scenario_1a_trips_routing(*await make_runner(root_agent))
            await scenario_1b_support_routing(*await make_runner(root_agent))
            await scenario_2a_mixed_intent(*await make_runner(root_agent))
            await scenario_3a_handoff(*await make_runner(root_agent))
            await scenario_4a_direct_answer(*await make_runner(root_agent))
            await scenario_5a_error_recovery(*await make_runner(orchestrator_error_demo))
            print_observability_notes()
        except KeyboardInterrupt:
            print("\n  Scenarios interrupted.\n")

        cont = input("  Continue to free REPL? [y/N]: ").strip().lower()
        if cont != "y":
            return

    await run_repl(*await make_runner(root_agent))


if __name__ == "__main__":
    asyncio.run(main())
