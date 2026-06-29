"""
demo.py — Day 04: PostgreSQL Tools + Redis Session Persistence
==============================================================
Google ADK · LiteLLM · OpenRouter · PostgreSQL · Redis

Runs six scripted scenarios that demonstrate the Day 04 upgrades,
then drops into a free REPL so you can explore further.
Type  q  to quit.

Run:
    docker compose up -d          # start Postgres + Redis
    cp .env.example .env          # fill in OPENROUTER_API_KEY
    python demo.py                # run all scenarios
    python demo.py --repl         # skip scenarios, go straight to REPL
"""

import asyncio
import logging
import os
import sys
import textwrap

from dotenv import load_dotenv
from google.genai import types

load_dotenv()

# ── Silence LiteLLM noise (same as Day 03) ────────────────────────────────
logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False

log = logging.getLogger("day04")
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

from agent import aria
from db import check_connection as pg_ok
from history import get_history, record_turn
from redis_client import (
    check_connection as redis_ok,
    load_session_state,
    save_session_state,
)
from session import make_runner

# ── Scenario guide ─────────────────────────────────────────────────────────
_GUIDE = """
  SCENARIO GUIDE — Day 04: PostgreSQL Tools + Redis Session Persistence
  ──────────────────────────────────────────────────────────────────────
  1  Booking lookup      "Check booking TB-1001 for me."
  2  Follow-up (state)   "What's the departure date?"       ← no ID needed
  3  Flight search       "Find flights from Mumbai to London."
  4  Cancel booking      "Cancel booking TB-1002."
  5  Already-cancelled   "Cancel booking TB-1003."          ← graceful error
  6  Session restart     [demo recreates runner, shows state survives]
     + History from DB   [prints full conversation history from PostgreSQL]
  ──────────────────────────────────────────────────────────────────────
"""

# ── Console helpers ────────────────────────────────────────────────────────

def _wrap(text: str, width: int = 74) -> str:
    prefix = "    "
    return textwrap.fill(text, width=width, initial_indent=prefix, subsequent_indent=prefix)


def _sep(char: str = "─", width: int = 70) -> None:
    print(f"  {char * width}")


def _build_message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


# ── ADK ask helper ─────────────────────────────────────────────────────────

async def _ask(
    runner,
    user_id: str,
    session_id: str,
    prompt: str,
    *,
    record: bool = True,
) -> str:
    """
    Send a prompt to the agent and return its reply.
    Optionally records both turns to PostgreSQL history and
    snapshots the session state to Redis after each exchange.
    """
    reply = ""
    tool_events: list[dict] = []

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=_build_message(prompt),
    ):
        # Collect tool call info for history logging
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    tool_events.append({"name": fc.name, "args": dict(fc.args or {})})

        if event.is_final_response():
            if event.content and event.content.parts:
                reply = event.content.parts[0].text or ""

    reply = reply.strip()

    if record:
        # Durable history → PostgreSQL
        record_turn(session_id, user_id, "user", prompt)
        record_turn(session_id, user_id, "model", reply, tool_calls=tool_events or None)

        # Working memory snapshot → Redis
        try:
            session_service = runner.session_service
            sess = await session_service.get_session(
                app_name=runner.app_name, user_id=user_id, session_id=session_id
            )
            if sess and sess.state:
                save_session_state(session_id, dict(sess.state))
        except Exception as exc:
            log.warning("Could not snapshot state to Redis: %s", exc)

    return reply


# ── Startup checks ─────────────────────────────────────────────────────────

def _check_services() -> bool:
    """Warn if Postgres or Redis is not reachable. Postgres is required."""
    pg_up = pg_ok()
    rd_up = redis_ok()

    if not pg_up:
        print(
            "\n[ERROR] PostgreSQL is not reachable.\n"
            "  Start it with:  docker compose up -d postgres\n"
            f"  Configured at:  {os.getenv('PG_HOST', 'localhost')}:{os.getenv('PG_PORT', '5432')}\n"
        )
        return False

    if not rd_up:
        print(
            "\n[WARNING] Redis is not reachable — session snapshots will be skipped.\n"
            "  Start it with:  docker compose up -d redis\n"
            "  The demo will continue using PostgreSQL-backed sessions only.\n"
        )
    return True


# ── Scripted scenarios ─────────────────────────────────────────────────────

async def run_scenarios(runner, user_id: str, session_id: str) -> None:
    """Run the six fixed demonstration scenarios."""

    def _show(label: str, prompt: str, reply: str) -> None:
        print(f"\n  [{label}]  You: {prompt}")
        print(f"\n  [Aria]\n{_wrap(reply)}\n")

    # ── Scenario 1: Booking lookup ─────────────────────────────────────────
    _sep()
    print("  Scenario 1 — Booking lookup (queries PostgreSQL)")
    _sep()
    prompt = "Can you check the status of booking TB-1001?"
    reply = await _ask(runner, user_id, session_id, prompt)
    _show("S1", prompt, reply)

    # ── Scenario 2: Follow-up without repeating the booking ID ─────────────
    _sep()
    print("  Scenario 2 — Follow-up using session state (no ID repeated)")
    _sep()
    prompt = "What's the departure date for this booking?"
    reply = await _ask(runner, user_id, session_id, prompt)
    _show("S2", prompt, reply)

    # ── Scenario 3: Flight search ──────────────────────────────────────────
    _sep()
    print("  Scenario 3 — Flight search (queries PostgreSQL flights table)")
    _sep()
    prompt = "I want to fly from Mumbai to London. What flights are available?"
    reply = await _ask(runner, user_id, session_id, prompt)
    _show("S3", prompt, reply)

    # ── Scenario 4: Cancel a valid booking ─────────────────────────────────
    _sep()
    print("  Scenario 4 — Cancel booking TB-1002 (valid cancellation)")
    _sep()
    prompt = "Please cancel booking TB-1002."
    reply = await _ask(runner, user_id, session_id, prompt)
    _show("S4", prompt, reply)

    # ── Scenario 5: Already-cancelled booking ──────────────────────────────
    _sep()
    print("  Scenario 5 — Cancel already-cancelled booking TB-1003 (graceful error)")
    _sep()
    prompt = "Can you also cancel TB-1003?"
    reply = await _ask(runner, user_id, session_id, prompt)
    _show("S5", prompt, reply)

    # ── Scenario 6: Session restart ────────────────────────────────────────
    _sep()
    print("  Scenario 6 — Simulating process restart + session recovery")
    _sep()

    # Show what's in Redis right now
    cached = load_session_state(session_id)
    if cached:
        print(f"  Redis snapshot (before restart):  {cached}\n")
    else:
        print("  Redis: no snapshot found (Redis may be down — continuing with DB).\n")

    # Reconnect using the same IDs — state comes from PostgreSQL
    print("  [Restarting runner with the same session_id...]\n")
    runner2, _, _ = await make_runner(aria, user_id=user_id, session_id=session_id)

    prompt = "What do you know about my current booking?"
    reply = await _ask(runner2, user_id, session_id, prompt)
    _show("S6", prompt, reply)

    # ── Print durable conversation history from PostgreSQL ─────────────────
    _sep()
    print("  Durable conversation history (from PostgreSQL session_history table)")
    _sep()
    history = get_history(session_id)
    if history:
        for turn in history:
            ts = str(turn["created_at"])[:19]
            tools_note = ""
            if turn.get("tool_calls"):
                import json
                calls = turn["tool_calls"]
                if isinstance(calls, str):
                    calls = json.loads(calls)
                names = ", ".join(t.get("name", "?") for t in calls)
                tools_note = f"  [tools: {names}]"
            print(f"  {ts}  {turn['role']:6s}  {turn['content'][:80]}{tools_note}")
    else:
        print("  (No history found — PostgreSQL may be unavailable.)")
    print()


# ── Free REPL ──────────────────────────────────────────────────────────────

async def run_repl(runner, user_id: str, session_id: str) -> None:
    """Drop into a free-form conversation REPL."""
    _sep("═")
    print("  Free REPL — type any prompt or  q  to quit.")
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

        reply = await _ask(runner, user_id, session_id, prompt)
        print(f"\n  [Aria]\n{_wrap(reply)}\n")

    print("  ── session ended ──\n")


# ── Main ───────────────────────────────────────────────────────────────────

async def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "\n[ERROR] OPENROUTER_API_KEY is not set.\n"
            "  Copy .env.example → .env and fill in your key.\n"
        )
        return

    if not _check_services():
        return

    print("""
+======================================================================+
|   DAY 04 — PostgreSQL Tools + Redis Session Persistence             |
|   Google ADK · LiteLLM · OpenRouter · psycopg2 · redis-py          |
+======================================================================+""")
    print(_GUIDE)

    repl_only = "--repl" in sys.argv

    runner, user_id, session_id = await make_runner(aria)
    print(f"  user_id:    {user_id}")
    print(f"  session_id: {session_id}\n")

    if not repl_only:
        try:
            await run_scenarios(runner, user_id, session_id)
        except KeyboardInterrupt:
            print("\n  Scenarios interrupted.\n")

        cont = input("  Continue to free REPL? [y/N]: ").strip().lower()
        if cont != "y":
            return

    await run_repl(runner, user_id, session_id)


if __name__ == "__main__":
    asyncio.run(main())
