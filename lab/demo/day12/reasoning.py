"""
reasoning.py — Day 12: turns ADK's tool-calling loop into visible
Thought / Action / Observation steps, plus reflection and loop-exit
detection.

ADK's Runner already runs the ReAct loop for us (feed tool results back to
the model until it stops calling tools). This module just narrates it:
every function_call/function_response pair becomes an Action/Observation
step, a constraint-revision turn becomes a Reflection step, and the reason
the loop stopped becomes an Exit step.
"""

import json
from dataclasses import dataclass, field

from google.genai import types

_REFLECTION_MARKERS = (
    "actually",
    "instead",
    "i said",
    "i meant",
    "rather have",
    "too expensive",
    "too pricey",
)


@dataclass
class ReasoningStep:
    kind: str  # "reflection" | "action" | "observation" | "exit"
    label: str
    detail: str = ""


@dataclass
class TurnResult:
    final_text: str = ""
    final_author: str = ""
    steps: list[ReasoningStep] = field(default_factory=list)
    exit_reason: str = ""
    tool_call_count: int = 0
    is_reflection: bool = False


def _looks_like_reflection(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _REFLECTION_MARKERS)


async def run_turn(runner, user_id: str, session_id: str, message: str, turn_index: int) -> TurnResult:
    """Run one user turn through the ADK Runner and narrate the reasoning loop.

    Args:
        turn_index: 0 for the first message in the session, 1+ thereafter.
            Reflection is only detected on follow-up turns.
    """
    result = TurnResult()

    if turn_index > 0 and _looks_like_reflection(message):
        result.is_reflection = True
        result.steps.append(
            ReasoningStep(
                kind="reflection",
                label="Constraint revised",
                detail=f'Traveller revised a constraint this turn: "{message}"',
            )
        )

    exhausted = False
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=message)]),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if fc := getattr(part, "function_call", None):
                    result.tool_call_count += 1
                    args = dict(fc.args or {})
                    result.steps.append(
                        ReasoningStep(kind="action", label=fc.name, detail=json.dumps(args))
                    )
                if fr := getattr(part, "function_response", None):
                    resp = fr.response or {}
                    if isinstance(resp, dict) and resp.get("exhausted"):
                        exhausted = True
                    result.steps.append(
                        ReasoningStep(
                            kind="observation",
                            label=fr.name,
                            detail=json.dumps(resp)[:800],
                        )
                    )

        if event.is_final_response() and event.content and event.content.parts:
            text = event.content.parts[0].text
            if text:
                result.final_text = text
                result.final_author = event.author

    if exhausted:
        result.exit_reason = (
            "exhausted — every known candidate for this query was returned "
            "in one search; nothing left to check"
        )
    elif result.tool_call_count >= 3:
        result.exit_reason = (
            f"stopped after {result.tool_call_count} tool calls — the model judged "
            "it had enough information to answer"
        )
    elif result.tool_call_count > 0:
        result.exit_reason = f"stopped after {result.tool_call_count} tool call(s) — sufficient to answer"
    else:
        result.exit_reason = "no tools needed — answered directly"

    result.steps.append(ReasoningStep(kind="exit", label="Loop exit", detail=result.exit_reason))
    return result
