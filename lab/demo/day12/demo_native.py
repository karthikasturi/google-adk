"""
demo_native.py — Day 12: the framework-native counterparts in action
=======================================================================
Runs the planner scenarios through the ADK-native stack:

  - ReAct      → agent_native.py (PlanReActPlanner) prints the model's own
                 /*PLANNING*/, /*REASONING*/, /*ACTION*/, /*REPLANNING*/,
                 /*FINAL_ANSWER*/ tags instead of reasoning.py's inferred steps.
  - Observability → tracing_otel.py routes ADK's built-in OpenTelemetry spans
                 to LangSmith automatically (no per-turn export code).

Compare with demo.py (the hand-rolled versions). This file is additive and
imports the same tools/session; nothing else in the demo changes.

Run:
    python demo_native.py
"""

import asyncio
import logging
import os
import textwrap

from dotenv import load_dotenv
from google.genai import types

load_dotenv()

logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False

from agent_native import root_agent
from session import make_runner
from tracing_otel import setup_langsmith_otel, shutdown_otel

_FINAL_ANSWER_TAG = "/*FINAL_ANSWER*/"


def _final_answer(text: str) -> str:
    """Strip the PlanReActPlanner tags, returning just the user-facing answer."""
    if _FINAL_ANSWER_TAG in text:
        text = text.rsplit(_FINAL_ANSWER_TAG, 1)[1]
    return text.strip()


def _wrap(text: str, width: int = 74) -> str:
    return textwrap.fill(text, width=width, initial_indent="    ", subsequent_indent="    ")


def _sep(char: str = "─", width: int = 70) -> None:
    print(f"  {char * width}")


async def _ask(runner, user_id, session_id, prompt, label):
    """Run one turn; print the planner's native reasoning text + tool calls."""
    reasoning_chunks: list[str] = []
    tool_calls: list[str] = []

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if fc := getattr(part, "function_call", None):
                    tool_calls.append(f"{fc.name}({dict(fc.args or {})})")
                if txt := getattr(part, "text", None):
                    reasoning_chunks.append(txt)

    print(f"\n  [{label}]  You: {prompt}")
    print("\n  Native ReAct output (PlanReActPlanner tags emitted by the model):")
    raw = "\n".join(c.strip() for c in reasoning_chunks if c.strip())
    for line in raw.splitlines():
        print(f"    {line}")
    if tool_calls:
        print("\n  Tool calls (also auto-traced as OTel spans → LangSmith):")
        for tc in tool_calls:
            print(f"    • {tc}")
    answer = _final_answer(raw)
    print(f"\n  [TravelBot]\n{_wrap(answer or '(see FINAL_ANSWER above)')}\n")


async def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("\n[ERROR] OPENROUTER_API_KEY is not set. Copy .env.example → .env.\n")
        return

    provider = setup_langsmith_otel()
    print("""
+======================================================================+
|   DAY 12 (native) — PlanReActPlanner + OpenTelemetry → LangSmith    |
+======================================================================+""")
    if provider:
        print("  OpenTelemetry → LangSmith: ON (ADK spans export automatically)\n")
    else:
        print("  OpenTelemetry → LangSmith: OFF (set LANGSMITH_API_KEY to enable)\n")

    runner, user_id, session_id = await make_runner(root_agent)

    _sep()
    print("  Native ReAct loop + replanning (compare demo.py scenario group 1)")
    _sep()
    await _ask(
        runner, user_id, session_id,
        "I want to fly from London to Tokyo next month. My budget is £900 "
        "all-in and I'd prefer a direct flight if possible.",
        "1",
    )
    await _ask(
        runner, user_id, session_id,
        "Actually I'd rather have a direct flight even if it costs a bit more. "
        "What's the cheapest direct option?",
        "1 replanning",
    )

    _sep()
    print("  Native loop termination (compare demo.py scenario group 2)")
    _sep()
    await _ask(
        runner, user_id, session_id,
        "I want the absolute cheapest flight to anywhere in Asia, departing "
        "any day in the next 60 days, under £400.",
        "2",
    )

    if provider:
        shutdown_otel()
        print("  Spans flushed to LangSmith.\n")


if __name__ == "__main__":
    asyncio.run(main())
