"""
scenario_06.py -- Chatbot vs Agent Reasoning
---------------------------------------------
Concept: A chatbot gives a generic answer.
         An agent reasons about the user's goal and provides structured
         guidance that helps the user make a decision.

Run standalone:
    python scenario_06.py
"""

import asyncio

from common import ask, divider, label, make_runner, wrap

CHATBOT_PROMPT = "You are a helpful assistant. Answer the user's question."

AGENT_PROMPT = """
You are a travel decision-support assistant.
When a traveler asks for a recommendation, reason step by step:
  1. Identify the traveler's likely goal or constraint.
  2. Weigh the trade-offs (rest, cost, time, arrival convenience).
  3. Give a structured recommendation with brief reasoning.
  4. Close with a clarifying question if you need more context.
Keep the response focused and actionable.
""".strip()


async def run() -> None:
    divider("SCENARIO 6 -- Chatbot vs Agent Reasoning")
    print("""
  Concept: A chatbot gives a generic answer.
  An agent reasons about the user's goal and provides structured guidance
  that helps the user make a decision.
    """)

    question = (
        "Can you help me decide whether I should take a night flight "
        "or a morning flight to Singapore?"
    )

    runner_chatbot, uid_c, sid_c = await make_runner(CHATBOT_PROMPT)
    label("USER")
    print(wrap(question))
    reply_chatbot = await ask(runner_chatbot, uid_c, sid_c, question)
    label("AGENT (chatbot-style instruction)")
    print(wrap(reply_chatbot))

    runner_agent, uid_a, sid_a = await make_runner(AGENT_PROMPT)
    label("USER (same question, agent-style instruction)")
    print(wrap(question))
    reply_agent = await ask(runner_agent, uid_a, sid_a, question)
    label("AGENT (decision-support instruction)")
    print(wrap(reply_agent))

    print("""
  --- Comparison point ---------------------------------------------------
  Chatbot: answers the question as asked -- surface-level response.
  Agent:   reasons about trade-offs, gives structured advice, and
           may ask a clarifying question -- goal-oriented behavior.
  ------------------------------------------------------------------------""")


if __name__ == "__main__":
    asyncio.run(run())
