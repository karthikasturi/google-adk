"""
db.py — PostgreSQL connection pool (v3+)
-----------------------------------------
Provides a thread-safe psycopg2 connection pool.
"""

import logging
from contextlib import contextmanager
from typing import Generator

import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor

from settings import settings

log = logging.getLogger(__name__)

_pool: pg_pool.ThreadedConnectionPool | None = None


def _get_pool() -> pg_pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = pg_pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=settings.pg_dsn,
        )
        log.info("PostgreSQL connection pool created (%s:%s/%s)", settings.pg_host, settings.pg_port, settings.pg_db)
    return _pool


@contextmanager
def _get_conn() -> Generator:
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def query_one(sql: str, params=None) -> dict | None:
    """Execute a SELECT and return the first row as a dict, or None."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None


def query_all(sql: str, params=None) -> list[dict]:
    """Execute a SELECT and return all rows as a list of dicts."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def execute(sql: str, params=None) -> int:
    """Execute an INSERT/UPDATE/DELETE; return the affected rowcount."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount


def check_connection() -> bool:
    """Return True if PostgreSQL is reachable."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception as exc:
        log.warning("PostgreSQL health check failed: %s", exc)
        return False
