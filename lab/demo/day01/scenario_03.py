"""
scenario_03.py -- In-scope vs Out-of-scope
-------------------------------------------
Concept: An agent is not a general-purpose responder.
         Its instruction defines what it will and will not do.

Run standalone:
    python scenario_03.py
"""

import asyncio

from common import FRIENDLY_SYSTEM_PROMPT, ask, divider, label, make_runner, wrap


async def run() -> None:
    divider("SCENARIO 3 -- In-scope vs Out-of-scope")
    print("""
  Concept: An agent is not a general-purpose responder.
  Its instruction defines what it will and will not do.
    """)

    runner, user_id, session_id = await make_runner(FRIENDLY_SYSTEM_PROMPT)

    q_in = "What is your baggage policy?"
    label("USER (in-scope)")
    print(wrap(q_in))
    reply_in = await ask(runner, user_id, session_id, q_in)
    label("AGENT")
    print(wrap(reply_in))

    runner2, user_id2, session_id2 = await make_runner(FRIENDLY_SYSTEM_PROMPT)
    q_out = "Can you write a Python script for me?"
    label("USER (out-of-scope)")
    print(wrap(q_out))
    reply_out = await ask(runner2, user_id2, session_id2, q_out)
    label("AGENT")
    print(wrap(reply_out))

    print("""
  --- Comparison point ---------------------------------------------------
  The travel assistant answers the baggage question and politely declines
  the coding request -- because the instruction defines its boundary.
  ------------------------------------------------------------------------""")


if __name__ == "__main__":
    asyncio.run(run())
