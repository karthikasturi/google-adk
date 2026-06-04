"""
shared/session.py — Session service factory (single swap point)
---------------------------------------------------------------
Supports three backends via SESSION_BACKEND env var:

    memory    — InMemorySessionService (v1–v2, no persistence)
    redis     — RedisSessionService (v3, fast cache, no SQL)
    database  — DatabaseSessionService (v3+, PostgreSQL, default)

All versions (v1, v2, v3) use make_runner() from here unchanged.
"""

import logging
import os
import uuid

from google.adk.runners import Runner
from google.adk.sessions import (
    DatabaseSessionService,
    InMemorySessionService,
    RedisSessionService,
)

log = logging.getLogger(__name__)

APP_NAME = "travelbot"


def get_session_service():
    """
    Return the active session service based on SESSION_BACKEND env var.

    Backends:
        memory   — InMemorySessionService: no persistence (v1–v2 default)
        redis    — RedisSessionService: sessions in Redis with TTL
        database — DatabaseSessionService: sessions in PostgreSQL (v3+ default)
    """
    backend = os.getenv("SESSION_BACKEND", "database").lower()

    if backend == "memory":
        log.info("Session backend: InMemory (no persistence)")
        return InMemorySessionService()

    if backend == "redis":
        try:
            from settings import settings
            svc = RedisSessionService(redis_url=settings.redis_url)
            log.info("Session backend: Redis (%s:%s)", settings.redis_host, settings.redis_port)
            return svc
        except Exception as exc:
            log.error("Redis session service unavailable: %s", exc)
            raise RuntimeError(
                "Cannot connect to Redis for session storage. "
                "Start it with:  docker compose up -d redis\n"
                f"Detail: {exc}"
            ) from exc

    # Default: database (PostgreSQL)
    try:
        from settings import settings
        svc = DatabaseSessionService(db_url=settings.adk_db_url)
        log.info(
            "Session backend: PostgreSQL (%s:%s/%s)",
            settings.pg_host, settings.pg_port, settings.pg_db,
        )
        return svc
    except Exception as exc:
        log.error("PostgreSQL session service unavailable: %s", exc)
        raise RuntimeError(
            "Cannot connect to PostgreSQL for session storage. "
            "Start it with:  docker compose up -d postgres\n"
            f"Detail: {exc}"
        ) from exc


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
