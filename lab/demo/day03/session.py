"""
session.py — Session service factory (single swap point)
----------------------------------------------------------
demo.py calls make_runner(root_agent) to get a Runner + session.
ADK Web creates its own session internally — this file is not used by it.

To move to persistent sessions, change ONLY get_session_service() here.
Everything else — tools, instruction, agent — stays unchanged.
"""

import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

APP_NAME = "day03-travel-demo"


def get_session_service():
    return InMemorySessionService()
    # ── Phase 3: swap to persistent ──────────────────────────────────────
    # import os
    # from google.adk.sessions import DatabaseSessionService
    # return DatabaseSessionService(db_url=os.environ["DATABASE_URL"])


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
