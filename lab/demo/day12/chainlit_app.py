"""
chainlit_app.py — Day 12: TravelBot UI with a collapsible Agent Reasoning panel
==================================================================================
Run:
    chainlit run chainlit_app.py -w

Each reply is followed by a collapsed "Agent Reasoning" step containing the
Thought/Action/Observation/Reflection/Exit trace for that turn (reasoning.py),
which is also exported to LangSmith if LANGSMITH_API_KEY is set (tracing.py).
"""

import logging
import os

import chainlit as cl
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

_STEP_TYPE = {"action": "tool", "observation": "tool", "reflection": "run", "exit": "run"}
_STEP_ICON = {"action": "🔧", "observation": "👁", "reflection": "🔄", "exit": "🏁"}


@cl.on_chat_start
async def start():
    if not os.environ.get("OPENROUTER_API_KEY"):
        await cl.Message(
            content="OPENROUTER_API_KEY is not set. Copy .env.example to .env and fill it in, then restart."
        ).send()
        return

    runner, user_id, session_id = await make_runner(root_agent)
    cl.user_session.set("runner", runner)
    cl.user_session.set("user_id", user_id)
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("turn_index", 0)

    await cl.Message(
        content=(
            "**TravelBot** is ready. Ask about flight search, business-class "
            "comparisons, cancellation policy, or booking status.\n\n"
            "Open **Agent Reasoning** under each reply to see the "
            "Thought → Action → Observation trace, including reflection and "
            "loop-exit steps."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    runner = cl.user_session.get("runner")
    user_id = cl.user_session.get("user_id")
    session_id = cl.user_session.get("session_id")
    turn_index = cl.user_session.get("turn_index")

    if runner is None:
        await cl.Message(content="Session not initialised — restart the chat.").send()
        return

    result = await run_turn(runner, user_id, session_id, message.content, turn_index)
    run_id = trace_turn(root_agent.name, user_id, session_id, message.content, result, turn_index)
    cl.user_session.set("turn_index", turn_index + 1)

    async with cl.Step(name="Agent Reasoning", type="run", default_open=False) as panel:
        panel.output = (
            f"exit: {result.exit_reason}"
            + (f"\nLangSmith run: {run_id}" if run_id else "\n(LangSmith not configured)")
        )
        for step in result.steps:
            icon = _STEP_ICON.get(step.kind, "")
            async with cl.Step(
                name=f"{icon} {step.kind}: {step.label}".strip(),
                type=_STEP_TYPE.get(step.kind, "run"),
            ) as sub:
                sub.output = step.detail

    await cl.Message(
        content=result.final_text or "(no response)",
        author=result.final_author or "TravelBot",
    ).send()
