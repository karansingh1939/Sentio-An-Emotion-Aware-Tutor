"""Durable tutor-turn receipts: one row per (session, request ID), replayed on retry.

Every function takes an open connection so the caller decides the transaction, as the
stream service must reserve, check and complete a turn inside its own boundaries.
"""

import json

from sqlalchemy import text


def fail_running(connection):
    """Mark turns left running by an earlier process as failed; nothing replays them."""
    connection.execute(text("UPDATE chat_requests SET status='failed' WHERE status='running'"))


def find(connection, owner, session_id, request_id):
    """The owner's saved receipt for this request, or None."""
    return (
        connection.execute(
            text(
                "SELECT * FROM chat_requests WHERE session_id=:session AND request_id=:request AND student_id=:owner"
            ),
            {"owner": owner, "session": session_id, "request": request_id},
        )
        .mappings()
        .first()
    )


def reserve(connection, owner, session_id, request_id, fingerprint, message, context, now):
    """Record the turn as running, replacing an earlier failed attempt with the same ID."""
    connection.execute(
        text(
            "INSERT OR REPLACE INTO chat_requests (session_id,request_id,student_id,fingerprint,status,updated_at,message,context) VALUES (:session,:request,:owner,:fingerprint,'running',:now,:message,:context)"
        ),
        {
            "owner": owner,
            "session": session_id,
            "request": request_id,
            "fingerprint": fingerprint,
            "now": now,
            "message": message,
            "context": context,
        },
    )


def complete(connection, owner, session_id, request_id, result, now):
    connection.execute(
        text(
            "UPDATE chat_requests SET status='complete', result_json=:result,updated_at=:now WHERE session_id=:session AND request_id=:request AND student_id=:owner"
        ),
        {
            "owner": owner,
            "session": session_id,
            "request": request_id,
            "result": json.dumps(result),
            "now": now,
        },
    )


def fail(connection, session_id, request_id, now):
    """Mark the turn failed unless it already completed."""
    connection.execute(
        text(
            "UPDATE chat_requests SET status='failed',updated_at=:now WHERE session_id=:session AND request_id=:request AND status!='complete'"
        ),
        {"session": session_id, "request": request_id, "now": now},
    )


def completed_turns(connection, owner, session_id, context, limit, offset):
    """Completed turns saved under this study context, newest first."""
    return (
        connection.execute(
            text(
                "SELECT request_id,message,result_json,updated_at FROM chat_requests WHERE student_id=:owner AND session_id=:session AND context=:context AND status='complete' ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"
            ),
            {
                "owner": owner,
                "session": session_id,
                "context": context,
                "limit": limit,
                "offset": offset,
            },
        )
        .mappings()
        .all()
    )
