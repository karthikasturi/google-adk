"""
demo.py — TravelBot evolving project runner
============================================
Google ADK · LiteLLM · OpenRouter · Session persistence (v3+)

Run a specific version or step through them in order:
    python demo.py         ← menu to pick v1, v2, or v3
    python demo.py v1      ← jump straight to v1
    python demo.py v2      ← jump straight to v2
    python demo.py v3      ← jump straight to v3

Type  q  to quit the current REPL.
After each version finishes, you're offered the next so you can see the evolution live.

V3-specific:
    SESSION_BACKEND=memory    python demo.py v3    ← in-memory (no persistence)
    SESSION_BACKEND=redis     python demo.py v3    ← Redis-backed sessions
    SESSION_BACKEND=database  python demo.py v3    ← PostgreSQL (default)
"""

import asyncio
import os
import sys
import textwrap
from pathlib import Path

from dotenv import load_dotenv
from google.genai import types

# ── Path setup (shared/ and vN/ are siblings of this file) ─────────────────
_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))

# Load .env from this directory before any API key checks
load_dotenv(_ROOT / ".env")


# ── Console helpers ─────────────────────────────────────────────────────────

def _wrap(text: str) -> str:
    prefix = "    "
    return textwrap.fill(
        text, width=74, initial_indent=prefix, subsequent_indent=prefix
    )


def _build_message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


# ── ADK ask helper ──────────────────────────────────────────────────────────

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


# ── Per-version config ──────────────────────────────────────────────────────

_V1_GUIDE = """
  TravelBot v1 — Basic Travel Assistant (no tools)
  ─────────────────────────────────────────────────
  Try:  "Help me plan a trip to Singapore."
        "What documents do I need for Japan?"
        "Can you book a flight for me?"   ← no tools, Aria explains
"""

_V2_GUIDE = """
  TravelBot v2 — Tools + Session State (in-memory)
  ──────────────────────────────────────────────────────────────────
  1  Flight status     "I'm flying on AI-204. Can you check the status?"
  2  Invalid flight    "Check flight ZZ-999."
  3  Hotel + name      "My name is Priya. I need a hotel in Tokyo."
                       "Find one near the station."          ← follow-up
  4  ToolContext state "What do you know about my trip so far?"
  ──────────────────────────────────────────────────────────────────
  All prompts run in ONE session — state (name, city, flight) accumulates.
"""

_V3_GUIDE = """
  TravelBot v3 — PostgreSQL Tools + Persistent Sessions
  ──────────────────────────────────────────────────────────────────
  1  Booking lookup    "Check booking TB-1001 for me."
  2  Follow-up (state) "What's the departure date?"         ← no ID needed
  3  Flight search     "Find flights from Mumbai to London."
  4  Cancel booking    "Cancel booking TB-1002."
  5  Already-cancelled "Cancel TB-1003."                    ← graceful error
  6  Session state     "What do you know about my trip?"   ← session context
  ──────────────────────────────────────────────────────────────────
  Requires:  docker compose up -d postgres redis
  Session backend: SESSION_BACKEND=database|redis|memory python demo.py v3
"""


# ── REPL for a single version ───────────────────────────────────────────────

async def _run_version(version: str) -> None:
    if version == "v1":
        from v1.agent import aria
        guide = _V1_GUIDE
        label = "TravelBot v1 — Basic Agent (no tools)"
    elif version == "v2":
        from v2.agent import aria
        guide = _V2_GUIDE
        label = "TravelBot v2 — Tools + Session State (in-memory)"
    else:  # v3
        from v3.agent import aria
        guide = _V3_GUIDE
        label = "TravelBot v3 — PostgreSQL Tools + Persistent Sessions"

    from shared.session import make_runner
    runner, user_id, session_id = await make_runner(aria)

    print(f"\n{'':=<70}")
    print(f"  {label}")
    print(f"  Model: google/gemini-2.5-flash  via OpenRouter + LiteLLM")
    print(f"{'':=<70}")
    print(guide)

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

    print(f"  ── {version} session ended. ──\n")


# ── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "\n[ERROR] OPENROUTER_API_KEY is not set.\n"
            "Add it to a .env file:  OPENROUTER_API_KEY=your-key-here\n"
        )
        return

    arg = sys.argv[1].lower() if len(sys.argv) > 1 else None

    if arg in ("v1", "v2", "v3"):
        await _run_version(arg)
        return

    # Interactive menu
    print("""
+======================================================================+
|            TravelBot — Evolving Agent Demo (Google ADK)             |
+======================================================================+

  This project shows how an agent evolves across versions:
    v1 — plain LlmAgent, system prompt only (no tools)
    v2 — adds tool calling and ToolContext session state
    v3 — upgrades to PostgreSQL tools and persistent sessions

  Run a specific version:
    python demo.py v1
    python demo.py v2
    python demo.py v3 (requires: docker compose up -d postgres redis)

  Session backend for v3:
    SESSION_BACKEND=memory    python demo.py v3    (no persistence)
    SESSION_BACKEND=redis     python demo.py v3    (Redis-only)
    SESSION_BACKEND=database  python demo.py v3    (PostgreSQL, default)
""")

    choice = input("  Start with v1, v2, or v3? [v1/v2/v3/q]: ").strip().lower()
    if choice == "q" or choice == "":
        return

    if choice not in ("v1", "v2", "v3"):
        print("  Invalid choice. Run:  python demo.py v1  |  v2  |  v3")
        return

    await _run_version(choice)

    if choice == "v1":
        next_choice = input(
            "  Continue with v2 to see tool calling added? [y/n]: "
        ).strip().lower()
        if next_choice == "y":
            await _run_version("v2")
            next_choice = input(
                "  Continue with v3 to see PostgreSQL + persistence? [y/n]: "
            ).strip().lower()
            if next_choice == "y":
                await _run_version("v3")
    elif choice == "v2":
        next_choice = input(
            "  Continue with v3 to see PostgreSQL + persistence? [y/n]: "
        ).strip().lower()
        if next_choice == "y":
            await _run_version("v3")


if __name__ == "__main__":
    asyncio.run(main())
