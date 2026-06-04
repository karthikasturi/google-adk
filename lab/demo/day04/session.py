"""
session.py — Session service factory (single swap point)
----------------------------------------------------------
Day 04 supports three session backends, selected via SESSION_BACKEND env var:

    SESSION_BACKEND=memory    — InMemorySessionService  (default for unit tests)
    SESSION_BACKEND=redis     — RedisSessionService     (Redis only, no SQL)
    SESSION_BACKEND=database  — DatabaseSessionService  (PostgreSQL, default)

Examples:
    SESSION_BACKEND=database python demo.py   ← full persistence (default)
    SESSION_BACKEND=redis    python demo.py   ← Redis-only sessions
    SESSION_BACKEND=memory   python demo.py   ← no persistence, tests only

Evolution path:
    Day 01–03: InMemorySessionService   (per-process, lost on restart)
    Day 04:    DatabaseSessionService   (PostgreSQL, survives restarts)  ← default
    Day 04:    RedisSessionService      (Redis-only, fast, no SQL needed)
    Day 05+:   Cloud-hosted session DB  (env var change only)
"""

import logging
import os
import uuid

from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService, InMemorySessionService
from adk_extra_services.sessions import RedisSessionService

import redis_client
from settings import settings

log = logging.getLogger(__name__)

APP_NAME = "day04-travelbot"


def get_session_service():
    """
    Return the active session service based on SESSION_BACKEND env var.

    Backends:
        memory   — InMemorySessionService: no persistence, useful for tests.
        redis    — RedisSessionService: sessions stored in Redis, survives
                   restarts as long as Redis is up. No SQL needed.
                   Set REDIS_HOST / REDIS_PORT / REDIS_PASSWORD in .env.
        database — DatabaseSessionService: sessions stored in PostgreSQL
                   via SQLAlchemy + asyncpg. Full durability. (default)
    """
    backend = os.getenv("SESSION_BACKEND", "database").lower()

    if backend == "memory":
        log.info("Session backend: InMemory (no persistence)")
        return InMemorySessionService()

    if backend == "redis":
        try:
            svc = RedisSessionService(redis_url=settings.redis_url)
            log.info(
                "Session backend: Redis (%s:%s)", settings.redis_host, settings.redis_port
            )
            return svc
        except Exception as exc:
            log.error("Redis session service unavailable: %s", exc)
            raise RuntimeError(
                "Cannot connect to Redis for session storage. "
                "Start it with:  docker compose up -d redis\n"
                f"Detail: {exc}"
            ) from exc

    # Default: database (PostgreSQL via asyncpg)
    try:
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
            "Start the database with:  docker compose up -d postgres\n"
            f"Detail: {exc}"
        ) from exc


async def make_runner(
    agent,
    user_id: str | None = None,
    session_id: str | None = None,
) -> tuple[Runner, str, str]:
    """
    Wrap an agent in a Runner with a session.

    - If session_id is None, a fresh session is created.
    - If session_id is provided, the existing session is reused (state
      is loaded from PostgreSQL automatically by DatabaseSessionService).

    Returns (runner, user_id, session_id).
    """
    session_service = get_session_service()
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    if user_id is None:
        user_id = f"user-{uuid.uuid4().hex[:6]}"

    if session_id is None:
        # Fresh session
        session_id = f"session-{uuid.uuid4().hex[:8]}"
        await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        log.info("Created new session: %s / %s", user_id, session_id)
    else:
        # Reconnect: verify the session exists, create if missing
        existing = await session_service.get_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        if existing is None:
            await session_service.create_session(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )
            log.info("Session not found in DB — created fresh: %s", session_id)
        else:
            log.info("Reconnected to existing session: %s", session_id)

    # Persist the session reference to Redis so the demo can recover it
    redis_client.save_session_ref(user_id, session_id)

    return runner, user_id, session_id
