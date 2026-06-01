"""
scenario_02.py -- Formal Travel Advisor
-----------------------------------------
Concept: Same question, same model -- but a formal instruction produces
         a completely different communication style.

Run standalone:
    python scenario_02.py
"""

import asyncio

from common import FORMAL_SYSTEM_PROMPT, ask, divider, label, make_runner, wrap


async def run() -> None:
    divider("SCENARIO 2 -- Formal Travel Advisor")
    print("""
  Concept: Same question, same model -- but a formal instruction produces
  a completely different communication style.
    """)

    runner, user_id, session_id = await make_runner(FORMAL_SYSTEM_PROMPT)
    question = "I need help planning a trip to Singapore."

    label("USER")
    print(wrap(question))
    reply = await ask(runner, user_id, session_id, question)
    label("AGENT (formal)")
    print(wrap(reply))

    print("""
  --- Comparison point ---------------------------------------------------
  Scenario 1 vs Scenario 2: same task, same model, different instruction.
  The instruction shapes voice, not just content.
  ------------------------------------------------------------------------""")


if __name__ == "__main__":
    asyncio.run(run())
