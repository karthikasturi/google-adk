"""
history.py — Durable conversation history (v3+)
-----------------------------------------------
Append-only session history stored in PostgreSQL.
"""

import json
import logging
from typing import Any

from db import execute, query_all

log = logging.getLogger(__name__)


def record_turn(
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    tool_calls: list[dict[str, Any]] | None = None,
) -> None:
    """Append one conversation turn to session_history."""
    try:
        execute(
            """
            INSERT INTO session_history (session_id, user_id, role, content, tool_calls)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                session_id,
                user_id,
                role,
                content,
                json.dumps(tool_calls) if tool_calls else None,
            ),
        )
    except Exception as exc:
        log.warning("History write failed (non-fatal): %s", exc)


def get_history(session_id: str) -> list[dict]:
    """Return all turns for a session ordered oldest-first."""
    try:
        return query_all(
            """
            SELECT role, content, tool_calls, created_at
            FROM session_history
            WHERE session_id = %s
            ORDER BY created_at ASC
            """,
            (session_id,),
        )
    except Exception as exc:
        log.warning("History read failed: %s", exc)
        return []
