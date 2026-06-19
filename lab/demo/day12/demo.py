"""
demo.py — Day 12: Reasoning Loops, Observability, and Evaluation
====================================================================
Google ADK · LiteLLM · OpenRouter · LangSmith · Chainlit · PromptFoo

Runs the five scripted scenario groups from the Day 12 demo prompt doc,
printing the Thought/Action/Observation reasoning trace and the loop-exit
reason for each turn, then drops into a free REPL.

Run:
    cp .env.example .env          # fill in OPENROUTER_API_KEY (+ optional LANGSMITH_API_KEY)
    python demo.py                # run all scenario groups
    python demo.py --repl         # skip scenarios, go straight to REPL

For the UI version with a collapsible "Agent Reasoning" panel:
    chainlit run chainlit_app.py

For the PromptFoo eval suite:
    cd promptfoo && npx promptfoo@latest eval
"""

import asyncio
import logging
import os
import sys
import textwrap

from dotenv import load_dotenv

load_dotenv()

logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False

from agent import root_agent
from reasoning import run_turn
from session import make_runner
from tracing import trace_turn

_GUIDE = """
  SCENARIO GUIDE — Day 12: Reasoning Loops, Observability, and Evaluation
  ──────────────────────────────────────────────────────────────────────
  1  ReAct loop          "London → Tokyo, £900 budget, prefer direct."
  1r Reflection          "Actually I'd rather have direct even if pricier."
  2  Loop termination    "Cheapest flight to anywhere in Asia, ≤60 days, <£400."
  3  Trace inspection    "Compare business class Dubai → New York for next Friday."
  5a Cheap path          "What's your cancellation policy?"
  5b Capable path        "Family of 5 with mobility/pet needs, Cape Town → Vancouver."
  ──────────────────────────────────────────────────────────────────────
  Scenario group 4 (PromptFoo eval) is not run here — see promptfoo/.
"""


def _wrap(text: str, width: int = 74) -> str:
    return textwrap.fill(text, width=width, initial_indent="    ", subsequent_indent="    ")


def _sep(char: str = "─", width: int = 70) -> None:
    print(f"  {char * width}")


async def _ask(runner, user_id, session_id, prompt, turn_index, label):
    """Run one turn, print its reasoning trace, export it to LangSmith, and
    return (reply_text, next_turn_index)."""
    result = await run_turn(runner, user_id, session_id, prompt, turn_index)
    run_id = trace_turn(root_agent.name, user_id, session_id, prompt, result, turn_index)

    print(f"\n  [{label}]  You: {prompt}")
    print("\n  Reasoning:")
    for step in result.steps:
        print(f"    [{step.kind:11s}] {step.label}: {step.detail[:200]}")
    if run_id:
        print(f"  (exported to LangSmith run {run_id})")
    print(f"\n  [TravelBot]\n{_wrap(result.final_text or '(no response)')}\n")

    return result.final_text, turn_index + 1


async def run_scenarios(runner, user_id: str, session_id: str) -> None:
    turn_index = 0

    # ── Scenario group 1: ReAct reasoning loop + reflection ──────────────────
    _sep()
    print("  Scenario group 1 — ReAct reasoning loop")
    _sep()
    _, turn_index = await _ask(
        runner, user_id, session_id,
        "I want to fly from London to Tokyo next month. My budget is £900 "
        "all-in and I'd prefer a direct flight if possible.",
        turn_index, "1",
    )
    _, turn_index = await _ask(
        runner, user_id, session_id,
        "Actually I'd rather have a direct flight even if it costs a bit "
        "more. What's the cheapest direct option?",
        turn_index, "1 reflection",
    )

    # ── Scenario group 2: Loop termination ───────────────────────────────────
    _sep()
    print("  Scenario group 2 — Loop termination")
    _sep()
    _, turn_index = await _ask(
        runner, user_id, session_id,
        "I want the absolute cheapest flight to anywhere in Asia, departing "
        "any day in the next 60 days, under £400.",
        turn_index, "2",
    )

    # ── Scenario group 3: Trace inspection ───────────────────────────────────
    _sep()
    print("  Scenario group 3 — LangSmith trace inspection")
    _sep()
    _, turn_index = await _ask(
        runner, user_id, session_id,
        "Compare business class options from Dubai to New York for next "
        "Friday. I want comfort and value, not just the cheapest.",
        turn_index, "3",
    )

    # ── Scenario group 5: Cost and latency awareness ─────────────────────────
    _sep()
    print("  Scenario group 5 — Cost and latency awareness (model routing)")
    _sep()
    _, turn_index = await _ask(
        runner, user_id, session_id,
        "What's your cancellation policy?",
        turn_index, "5a cheap path",
    )
    _, turn_index = await _ask(
        runner, user_id, session_id,
        "I'm travelling with two kids under 5, one elderly parent with "
        "mobility issues, and a large pet. I need the most practical route "
        "from Cape Town to Vancouver in December.",
        turn_index, "5b capable path",
    )


async def run_repl(runner, user_id: str, session_id: str, turn_index: int) -> None:
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

        _, turn_index = await _ask(runner, user_id, session_id, prompt, turn_index, "repl")

    print("  ── session ended ──\n")


async def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "\n[ERROR] OPENROUTER_API_KEY is not set.\n"
            "  Copy .env.example → .env and fill in your key.\n"
        )
        return

    if not os.environ.get("LANGSMITH_API_KEY"):
        print(
            "[INFO] LANGSMITH_API_KEY not set — reasoning traces will print to "
            "console only (not exported to LangSmith).\n"
        )

    print("""
+======================================================================+
|   DAY 12 — Reasoning Loops, Observability, and Evaluation           |
|   Google ADK · LiteLLM · OpenRouter · LangSmith · PromptFoo         |
+======================================================================+""")
    print(_GUIDE)

    repl_only = "--repl" in sys.argv
    runner, user_id, session_id = await make_runner(root_agent)
    print(f"  user_id:    {user_id}")
    print(f"  session_id: {session_id}\n")

    turn_index = 0
    if not repl_only:
        try:
            await run_scenarios(runner, user_id, session_id)
            turn_index = 6
        except KeyboardInterrupt:
            print("\n  Scenarios interrupted.\n")

        cont = input("  Continue to free REPL? [y/N]: ").strip().lower()
        if cont != "y":
            return

    await run_repl(runner, user_id, session_id, turn_index)


if __name__ == "__main__":
    asyncio.run(main())
