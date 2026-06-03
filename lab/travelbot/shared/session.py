"""
shared/session.py — Session service factory (single swap point)
----------------------------------------------------------------
Both v1 and v2 agents use make_runner() from here.

To move from in-memory to persistent sessions, change ONLY this file.
All agent files and tool files remain unchanged.

Evolution path:
    Phase 1 (v1–v2): InMemorySessionService   ← current
    Phase 2 (v3+):   DatabaseSessionService    ← swap here
    Phase 3 (final): Cloud-hosted session DB   ← env var change only
"""

import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

APP_NAME = "travelbot"


def get_session_service():
    return InMemorySessionService()
    # ── Phase 2: swap to persistent ──────────────────────────────────────
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
