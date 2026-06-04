"""
history.py — Durable conversation history in PostgreSQL
---------------------------------------------------------
Conversation turns are written here after each exchange.
This is separate from ADK's own session tables — it captures a clean
human-readable audit trail: who said what, when, and which tools were called.

Boundary:
  Session state  = short-lived working memory (Redis + ADK session)
  History        = durable, append-only record of every turn (PostgreSQL)

Public API:
    record_turn(session_id, user_id, role, content, tool_calls)
    get_history(session_id)   → list[dict]
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
    """
    Append one conversation turn to session_history.

    Args:
        session_id:  ADK session identifier.
        user_id:     User identifier.
        role:        'user' or 'model'.
        content:     The text of the turn.
        tool_calls:  Optional list of tool call records (name + args).
    """
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
        # History write failures are non-fatal — log and continue.
        log.warning("History write failed (non-fatal): %s", exc)


def get_history(session_id: str) -> list[dict]:
    """
    Return all turns for a session ordered oldest-first.
    Returns an empty list if the session is not found or the DB is down.
    """
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
