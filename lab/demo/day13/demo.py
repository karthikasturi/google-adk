"""
demo.py — Day 13: Guardrails & Production Readiness
=====================================================
Google ADK · LiteLLM · OpenRouter

Runs the five guardrail scenarios in adjacent domains. For each one it prints:
  - the user prompt (so the attack/ask is visible),
  - what the guardrail did (the "intercepted" indicator), read from session
    state["guardrail_events"],
  - the safe assistant response.

Run:
    cp .env.example .env          # set OPENROUTER_API_KEY
    python demo.py                # all five scenarios
    python demo.py 3              # just scenario 3
"""

import asyncio
import logging
import os
import sys
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

from agent import SCENARIOS, SCENARIOS_BY_ID
from session import make_runner


def _wrap(text: str, width: int = 74) -> str:
    out = []
    for para in text.split("\n"):
        out.append(textwrap.fill(para, width=width, initial_indent="    ",
                                 subsequent_indent="    ") if para.strip() else "")
    return "\n".join(out)


def _sep(char: str = "─", width: int = 70) -> None:
    print(f"  {char * width}")


async def run_scenario(scenario: dict) -> None:
    agent = scenario["agent"]
    runner, user_id, session_id = await make_runner(agent)

    _sep("═")
    print(f"  Scenario {scenario['id']} — {scenario['domain']}")
    print(f"  Guardrail: {scenario['guardrail']}")
    _sep("═")
    print(f"\n  User:\n{_wrap(scenario['prompt'])}\n")

    reply = ""
    tool_calls: list[str] = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=scenario["prompt"])]),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if fc := getattr(part, "function_call", None):
                    tool_calls.append(f"{fc.name}({dict(fc.args or {})})")
        if event.is_final_response() and event.content and event.content.parts:
            t = event.content.parts[0].text
            if t:
                reply = t

    # Read what the guardrails did from session state.
    session = await runner.session_service.get_session(
        app_name=runner.app_name, user_id=user_id, session_id=session_id
    )
    events = (session.state or {}).get("guardrail_events", [])

    print("  🛡  Guardrail activity:")
    if events:
        for ev in events:
            print(f"      [{ev['action'].upper()}] {ev['guardrail']} — {ev['detail']}")
    else:
        print("      (none fired — request was already safe)")

    if tool_calls:
        print("\n  Tool calls attempted:")
        for tc in tool_calls:
            print(f"      • {tc}")

    print(f"\n  Assistant:\n{_wrap(reply or '(no text response)')}\n")


async def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("\n[ERROR] OPENROUTER_API_KEY is not set. Copy .env.example → .env.\n")
        return

    print("""
+======================================================================+
|   DAY 13 — Guardrails & Production Readiness                        |
|   input injection · output PII · tool safety · scope · readiness    |
+======================================================================+""")

    if len(sys.argv) > 1:
        chosen = [SCENARIOS_BY_ID[a] for a in sys.argv[1:] if a in SCENARIOS_BY_ID]
        if not chosen:
            print(f"  Unknown scenario(s). Pick from: {', '.join(SCENARIOS_BY_ID)}")
            return
    else:
        chosen = SCENARIOS

    for scenario in chosen:
        try:
            await run_scenario(scenario)
        except Exception as exc:  # noqa: BLE001 — keep the demo going
            print(f"  [scenario {scenario['id']} error] {type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    asyncio.run(main())
