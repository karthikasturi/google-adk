"""
scenario_04.py -- Known Facts vs Unknown Live Data
----------------------------------------------------
Concept: A responsible agent does not invent live data it cannot access.

Run standalone:
    python scenario_04.py
"""

import asyncio

from common import FRIENDLY_SYSTEM_PROMPT, ask, divider, label, make_runner, wrap


async def run() -> None:
    divider("SCENARIO 4 -- Known Facts vs Unknown Live Data")
    print("""
  Concept: Agents should know what they know -- and what they don't.
  General travel knowledge is fine; live flight prices are not.
    """)

    runner, user_id, session_id = await make_runner(FRIENDLY_SYSTEM_PROMPT)

    q_known = "What documents do I need for international travel?"
    label("USER (general knowledge)")
    print(wrap(q_known))
    reply_known = await ask(runner, user_id, session_id, q_known)
    label("AGENT")
    print(wrap(reply_known))

    q_unknown = "What is the cheapest flight to Singapore tomorrow?"
    label("USER (live data -- model should not invent this)")
    print(wrap(q_unknown))
    reply_unknown = await ask(runner, user_id, session_id, q_unknown)
    label("AGENT")
    print(wrap(reply_unknown))

    print("""
  --- Comparison point ---------------------------------------------------
  First answer:  general guidance from established knowledge -- valid.
  Second answer: agent acknowledges it has no live pricing data -- correct.
  A chatbot might invent a price; a responsible agent does not.
  ------------------------------------------------------------------------""")


if __name__ == "__main__":
    asyncio.run(run())
