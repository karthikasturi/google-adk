"""
tracing.py — Day 12: LangSmith trace export for the reasoning loop
=====================================================================
Sends each completed turn to LangSmith as a root run with one child run
per ReasoningStep (action/observation/reflection/exit) — the trace tree
Scenario group 3 asks trainers to read (root span, child spans, where
time/cost is spent).

No-op if LANGSMITH_API_KEY is unset, so the rest of the demo (Chainlit UI,
PromptFoo eval) runs the same whether or not LangSmith is configured.
"""

import datetime
import json
import os
import uuid

from reasoning import TurnResult

_client = None
_client_checked = False


def _get_client():
    global _client, _client_checked
    if _client_checked:
        return _client
    _client_checked = True
    if not os.environ.get("LANGSMITH_API_KEY"):
        return None
    from langsmith import Client

    _client = Client()
    return _client


_RUN_TYPE_BY_KIND = {
    "action": "tool",
    "observation": "tool",
    "reflection": "chain",
    "exit": "chain",
}


def trace_turn(agent_name: str, user_id: str, session_id: str, message: str,
                turn_result: TurnResult, turn_index: int) -> str | None:
    """Export a completed turn to LangSmith. Returns the root run ID, or None
    if LangSmith isn't configured."""
    client = _get_client()
    if client is None:
        return None

    project = os.environ.get("LANGSMITH_PROJECT", "day12-travelbot")
    root_id = str(uuid.uuid4())
    start = datetime.datetime.now(datetime.timezone.utc)

    client.create_run(
        id=root_id,
        name=f"{agent_name} — turn {turn_index}",
        run_type="chain",
        inputs={"message": message},
        project_name=project,
        start_time=start,
        extra={
            "metadata": {
                "user_id": user_id,
                "session_id": session_id,
                "is_reflection": turn_result.is_reflection,
                "tool_call_count": turn_result.tool_call_count,
            }
        },
    )

    for step in turn_result.steps:
        child_id = str(uuid.uuid4())
        run_type = _RUN_TYPE_BY_KIND.get(step.kind, "chain")
        client.create_run(
            id=child_id,
            parent_run_id=root_id,
            name=f"{step.kind}: {step.label}",
            run_type=run_type,
            inputs={"kind": step.kind, "label": step.label},
            project_name=project,
            start_time=start,
        )
        client.update_run(
            child_id,
            outputs={"detail": step.detail},
            end_time=datetime.datetime.now(datetime.timezone.utc),
        )

    client.update_run(
        root_id,
        outputs={"final_text": turn_result.final_text, "exit_reason": turn_result.exit_reason},
        end_time=datetime.datetime.now(datetime.timezone.utc),
    )
    return root_id
