"""
provider.py — PromptFoo custom Python provider for Day 12 TravelBot
=======================================================================
Invoked by promptfoo as `python:provider.py` (see promptfooconfig.yaml).
Runs the prompt through the real ADK agent (agent.py) in a fresh session
and returns its final reply, plus the reasoning trace as metadata so
results can be inspected in the promptfoo viewer.

A test input may encode more than one user turn by separating them with
"\\n---\\n" — used by the "rejection and reflection" test case, where the
second turn corrects a constraint set in the first.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import root_agent  # noqa: E402
from reasoning import run_turn  # noqa: E402
from session import make_runner  # noqa: E402


async def _run_turns(turns: list[str]):
    runner, user_id, session_id = await make_runner(root_agent)
    result = None
    transcript = []
    for i, turn_text in enumerate(turns):
        result = await run_turn(runner, user_id, session_id, turn_text, i)
        transcript.append({"turn": turn_text, "reply": result.final_text})
    return result, transcript


def call_api(prompt: str, options: dict, context: dict) -> dict:
    turns = [t.strip() for t in prompt.split("\n---\n") if t.strip()]
    if not turns:
        return {"error": "empty prompt"}

    if not os.environ.get("OPENROUTER_API_KEY"):
        return {"error": "OPENROUTER_API_KEY is not set — copy ../.env.example to ../.env"}

    try:
        result, transcript = asyncio.run(_run_turns(turns))
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "output": result.final_text,
        "metadata": {
            "transcript": transcript,
            "exit_reason": result.exit_reason,
            "tool_call_count": result.tool_call_count,
            "is_reflection": result.is_reflection,
        },
    }
