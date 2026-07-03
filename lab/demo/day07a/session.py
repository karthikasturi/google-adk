"""
session.py — Session service factory (single swap point)
---------------------------------------------------------
demo.py calls make_runner(agent) to get a Runner + fresh session.
Day 07 uses in-memory sessions — the focus here is routing and
resilience, not session persistence (see Day 04 for that pattern).
"""

import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

APP_NAME = "day07-routing-demo"


def get_session_service():
    return InMemorySessionService()


async def make_runner(agent) -> tuple[Runner, str, str]:
    """
    Wrap an agent in a Runner with a fresh isolated session.
    Returns (runner, user_id, session_id).
    """
    session_service = get_session_service()
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    user_id = f"user-{uuid.uuid4().hex[:6]}"
    session_id = f"session-{uuid.uuid4().hex[:8]}"
    await session_service.create_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    return runner, user_id, session_id
