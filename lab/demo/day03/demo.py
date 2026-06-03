"""
demo.py — Day 03: Tool Calling and Session State
=================================================
Google ADK · LiteLLM · OpenRouter · In-memory sessions

Single continuous session — context accumulates across all turns.
Type any prompt freely; use the scenario guide below as a starting point.
Type  q  to quit.

Run:
    python demo.py
"""

import asyncio
import os
import textwrap

from agent import aria
from session import make_runner
from google.genai import types

# ── Scenario guide printed at startup ──────────────────────────────────────
_GUIDE = """
  SCENARIO GUIDE  (type freely or follow this order)
  ────────────────────────────────────────────────────────────────────
  1  Flight status     "I'm flying on AI-204. Can you check the status?"
  2  Invalid flight    "Check flight ZZ-999."
  3  Hotel + name      "My name is Priya. I need a hotel in Tokyo."
                       "Find one near the station."          ← follow-up
  4  ToolContext state "What do you know about my trip so far?"
  ────────────────────────────────────────────────────────────────────
  All prompts run in ONE session — state (name, city, flight) accumulates.
  Scenario 4 reads back exactly what the earlier tool calls wrote to state.
"""

# ── Console helpers ────────────────────────────────────────────────────────

def _wrap(text: str) -> str:
    prefix = "    "
    return textwrap.fill(
        text, width=74, initial_indent=prefix, subsequent_indent=prefix
    )


def _build_message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


# ── ADK ask helper ─────────────────────────────────────────────────────────

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


# ── Main REPL ──────────────────────────────────────────────────────────────

async def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "\n[ERROR] OPENROUTER_API_KEY is not set.\n"
            "Add it to a .env file:  OPENROUTER_API_KEY=your-key-here\n"
        )
        return

    print("""
+======================================================================+
|     DAY 03 — Tool Calling and Session State  (Google ADK Demo)      |
|   Model : google/gemini-2.5-flash      via OpenRouter + LiteLLM    |
+======================================================================+""")
    print(_GUIDE)

    runner, user_id, session_id = await make_runner(aria)

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

    print("  Goodbye.\n")


if __name__ == "__main__":
    asyncio.run(main())
