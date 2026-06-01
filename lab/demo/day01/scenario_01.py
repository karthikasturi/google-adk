"""
scenario_01.py -- Friendly Travel Assistant
--------------------------------------------
Concept: A system prompt makes the model adopt a specific persona.
         Here the assistant is warm and conversational.

Run standalone:
    python scenario_01.py
"""

import asyncio

from common import FRIENDLY_SYSTEM_PROMPT, ask, divider, label, make_runner, wrap


async def run() -> None:
    divider("SCENARIO 1 -- Friendly Travel Assistant")
    print("""
  Concept: A system prompt makes the model adopt a specific persona.
  Here the assistant is warm and conversational.
    """)

    runner, user_id, session_id = await make_runner(FRIENDLY_SYSTEM_PROMPT)
    question = "I need help planning a trip to Singapore."

    label("USER")
    print(wrap(question))
    reply = await ask(runner, user_id, session_id, question)
    label("AGENT (friendly)")
    print(wrap(reply))


if __name__ == "__main__":
    asyncio.run(run())
