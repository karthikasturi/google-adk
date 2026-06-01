"""
scenario_05.py -- Session Memory (Interactive Chat)
------------------------------------------------------
Concept: The Runner maintains conversation history within a session.
         Each message you type is remembered -- the agent can refer back
         to anything said earlier in the same session.

When called from demo.py: runs a two-turn scripted demo.
When run standalone:      starts an interactive chat loop.

Run standalone:
    python scenario_05.py
"""

import asyncio
import sys

from common import FRIENDLY_SYSTEM_PROMPT, ask, divider, label, make_runner, wrap


# ── Scripted demo (called by demo.py) ─────────────────────────────────────

async def run() -> None:
    divider("SCENARIO 5 -- Session Memory (Multi-turn)")
    print("""
  Concept: The Runner maintains conversation history within a session.
  Turn 2 can refer to information from Turn 1 without re-stating it.
    """)

    runner, user_id, session_id = await make_runner(FRIENDLY_SYSTEM_PROMPT)

    q1 = "I'm traveling to Singapore next week."
    label("USER -- Turn 1")
    print(wrap(q1))
    reply1 = await ask(runner, user_id, session_id, q1)
    label("AGENT -- Turn 1")
    print(wrap(reply1))

    q2 = "What should I pack?"
    label("USER -- Turn 2 (no destination repeated)")
    print(wrap(q2))
    reply2 = await ask(runner, user_id, session_id, q2)
    label("AGENT -- Turn 2 (should reference Singapore from Turn 1)")
    print(wrap(reply2))

    print("""
  --- Comparison point ---------------------------------------------------
  Without session memory, Turn 2 produces a generic packing list.
  With session memory, it is tailored to Singapore (warm climate,
  possible rain, etc.) -- because the context was preserved.
  ------------------------------------------------------------------------""")


# ── Interactive chat (standalone) ─────────────────────────────────────────

async def interactive_chat() -> None:
    divider("SCENARIO 5 -- Interactive Travel Assistant Chat")
    print("""
  The agent remembers everything you say within this session.
  Try mentioning a destination, then ask follow-up questions without
  repeating it -- the agent will recall the context.

  Type  'quit' or 'exit' to end the session.
  Type  'reset' to start a fresh session (clears memory).
    """)

    runner, user_id, session_id = await make_runner(FRIENDLY_SYSTEM_PROMPT)
    turn = 0

    while True:
        # Prompt
        try:
            user_input = input("\n  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n  [Session ended]")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit"}:
            print("\n  [Session ended]  Goodbye!")
            break

        if user_input.lower() == "reset":
            runner, user_id, session_id = await make_runner(FRIENDLY_SYSTEM_PROMPT)
            turn = 0
            print("  [Memory cleared -- new session started]")
            continue

        turn += 1
        reply = await ask(runner, user_id, session_id, user_input)
        print(f"\n  Aria:\n{wrap(reply)}")

        if turn == 2:
            print(
                "\n  [Tip: notice that Aria remembers what you said earlier "
                "without you having to repeat it]"
            )


if __name__ == "__main__":
    asyncio.run(interactive_chat())
