"""
chainlit_app.py — Day 13: guardrails UI with a clear "intercepted" indicator
================================================================================
One chat profile per scenario domain (travel / banking / food / retail /
engineering). Whenever a guardrail fires on a turn, a red-flagged
"🛡 Guardrail intercepted" step is shown above the answer with what it did —
the "clear UI indicator" the demo asks for.

Run:
    chainlit run chainlit_app.py -w

Then pick a domain from the chat-profile selector and paste that scenario's
prompt (see README / demo.py).
"""

import logging
import os

import chainlit as cl
from dotenv import load_dotenv
from google.genai import types

load_dotenv()

logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False

from agent import SCENARIOS
from session import make_runner

_BY_PROFILE = {f"{s['domain']} ({s['guardrail']})": s for s in SCENARIOS}


@cl.set_chat_profiles
async def chat_profiles():
    return [
        cl.ChatProfile(
            name=name,
            markdown_description=(
                f"**{s['domain']}** — guardrail: `{s['guardrail']}`.\n\n"
                f"Try: _{s['prompt']}_"
            ),
        )
        for name, s in _BY_PROFILE.items()
    ]


@cl.on_chat_start
async def start():
    if not os.environ.get("OPENROUTER_API_KEY"):
        await cl.Message(content="OPENROUTER_API_KEY is not set — add it to .env and restart.").send()
        return

    profile = cl.user_session.get("chat_profile")
    scenario = _BY_PROFILE.get(profile, SCENARIOS[0])

    runner, user_id, session_id = await make_runner(scenario["agent"])
    cl.user_session.set("runner", runner)
    cl.user_session.set("user_id", user_id)
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("seen_events", 0)

    await cl.Message(
        content=(
            f"**{scenario['domain']}** assistant ready — guardrail: "
            f"`{scenario['guardrail']}`.\n\nSuggested prompt:\n\n> {scenario['prompt']}"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    runner = cl.user_session.get("runner")
    if runner is None:
        await cl.Message(content="Session not initialised — restart the chat.").send()
        return
    user_id = cl.user_session.get("user_id")
    session_id = cl.user_session.get("session_id")

    reply = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=message.content)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            t = event.content.parts[0].text
            if t:
                reply = t

    # Surface any guardrail activity from this turn as a clear indicator.
    session = await runner.session_service.get_session(
        app_name=runner.app_name, user_id=user_id, session_id=session_id
    )
    events = (session.state or {}).get("guardrail_events", [])
    seen = cl.user_session.get("seen_events", 0)
    new_events = events[seen:]
    cl.user_session.set("seen_events", len(events))

    if new_events:
        async with cl.Step(name="🛡 Guardrail intercepted", type="run", default_open=True) as step:
            step.output = "\n".join(
                f"[{e['action'].upper()}] {e['guardrail']} — {e['detail']}" for e in new_events
            )

    await cl.Message(content=reply or "(no text response)").send()
