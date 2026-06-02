"""
demo.py — Day 01: What is an AI Agent?
=======================================
Google ADK · LiteLLM · OpenRouter · In-memory sessions

Orchestrates all six scenarios in sequence.
Each scenario is in its own file (scenario_01.py … scenario_06.py).
Shared helpers and configuration live in common.py.

Run:
    python demo.py

Run a single scenario:
    python scenario_01.py
"""

import asyncio
import os

import common  # triggers load_dotenv() + asyncio logging suppression at module level

import scenario_01
import scenario_02
import scenario_03
import scenario_04
import scenario_05
import scenario_06


async def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "\n[ERROR] OPENROUTER_API_KEY is not set.\n"
            "Create a .env file in this directory with:\n"
            "  OPENROUTER_API_KEY=your-key-here\n"
        )
        return

    print("""
+======================================================================+
|           DAY 01 -- What Is an AI Agent?  (Google ADK Demo)         |
|   Model  : google/gemini-2.5-flash      via OpenRouter + LiteLLM   |
+======================================================================+

  This demo walks through six scenarios that illustrate how an AI agent
  differs from a chatbot.  Each scenario is self-contained.
    """)

    await scenario_01.run()
    await scenario_02.run()
    await scenario_03.run()
    await scenario_04.run()
    await scenario_05.run()
    await scenario_06.run()

    print("\n" + "=" * 70)
    print("  Demo complete.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
