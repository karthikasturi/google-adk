"""
redis_client.py — Redis session state cache (v3+)
--------------------------------------------------
Session working memory snapshots with TTL.
All failures are caught and logged — app continues without caching.
"""

import json
import logging

import redis

from settings import settings

log = logging.getLogger(__name__)

_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            decode_responses=True,
            socket_connect_timeout=3,
        )
    return _client


def save_session_state(session_id: str, state: dict) -> None:
    """Snapshot session state to Redis with TTL."""
    try:
        key = f"travelbot:state:{session_id}"
        _get_redis().setex(key, settings.redis_session_ttl, json.dumps(state))
    except redis.RedisError as exc:
        log.warning("Redis unavailable — state not cached: %s", exc)


def load_session_state(session_id: str) -> dict | None:
    """Load session state from Redis. Returns None if missing or Redis down."""
    try:
        raw = _get_redis().get(f"travelbot:state:{session_id}")
        return json.loads(raw) if raw else None
    except redis.RedisError as exc:
        log.warning("Redis unavailable — cannot load cached state: %s", exc)
        return None


def check_connection() -> bool:
    """Return True if Redis is reachable."""
    try:
        return _get_redis().ping()
    except redis.RedisError:
        return False
