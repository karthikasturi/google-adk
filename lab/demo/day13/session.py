"""
session.py — ADK session factory for the Day 13 guardrails demo
"""

import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

APP_NAME = "day13-guardrails"


async def make_runner(agent) -> tuple[Runner, str, str]:
    """Wrap an agent in a Runner with a fresh isolated session.

    Returns (runner, user_id, session_id).
    """
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)
    user_id = f"user-{uuid.uuid4().hex[:6]}"
    session_id = f"session-{uuid.uuid4().hex[:8]}"
    await session_service.create_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    return runner, user_id, session_id
