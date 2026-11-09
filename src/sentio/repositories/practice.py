"""Saved practice access and atomic card review receipts."""

import json
import time
from contextlib import contextmanager

from sqlalchemy import text

from sentio.jobs.control import WorkCancelled
from sentio.repositories.planning import active_goal


class ReviewConflict(ValueError):
    pass


class PracticeRepository:
    def __init__(self, engine):
        self.engine = engine

    def snapshot(self, session, connection=None):
        from contextlib import nullcontext

        from sentio.repositories.courses import COURSE_PREFIX, expand_source

        source = session.metadata.get("document_id")
        with nullcontext(connection) if connection is not None else self.engine.connect() as conn:
            selected = expand_source(conn, session.student_id, source)
            selected = selected if isinstance(selected, list) else [selected]
            documents = [
                list(row)
                for row in conn.execute(
                    text("SELECT id,checksum FROM documents WHERE student_id=:owner ORDER BY id"),
                    {"owner": session.student_id},
                )
                if source == "all" or row[0] in selected
            ]
            goal = active_goal(conn, session.student_id, session.metadata.get("goal_id"))
        is_course = isinstance(source, str) and source.startswith(COURSE_PREFIX)
        if (
            source not in (None, "none", "all")
            and not is_course
            and {r[0] for r in documents} != set(selected)
        ):
            raise WorkCancelled("Selected notes are no longer available. Choose sources and retry.")
        return {
            "subject": session.subject,
            "topic": session.topic,
            "difficulty": session.difficulty,
            "source": source,
            "topics": session.metadata.get("topic_ids") or [],
            "documents": documents,
            "goal": goal,
        }

    @contextmanager
    def publication(self, session, snapshot, deck_id=None, student_id=None):
        from types import SimpleNamespace

        owner_id = session.student_id if session else student_id
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                owner = connection.execute(
                    text("SELECT 1 FROM student_accounts WHERE student_id=:owner"),
                    {"owner": owner_id},
                ).scalar()
                stored = (
                    connection.execute(
                        text(
                            "SELECT data_json FROM sessions WHERE session_id=:id AND student_id=:owner"
                        ),
                        {"id": session.session_id, "owner": session.student_id},
                    ).scalar()
                    if session
                    else None
                )
                if not owner or (session and not stored):
                    raise WorkCancelled("Study account or session is no longer available.")
                if session:
                    data = json.loads(stored)
                    current = SimpleNamespace(
                        student_id=session.student_id,
                        subject=data["subject"],
                        topic=data["topic"],
                        difficulty=data["difficulty"],
                        metadata=data.get("metadata", {}),
                    )
                    if (
                        data.get("status") != "active"
                        or self.snapshot(current, connection) != snapshot
                    ):
                        raise WorkCancelled("Study context changed. Retry with the current notes.")
                if (
                    deck_id
                    and not connection.execute(
                        text(
                            "SELECT 1 FROM flashcard_decks WHERE deck_id=:deck AND student_id=:owner"
                        ),
                        {"deck": deck_id, "owner": owner_id},
                    ).scalar()
                ):
                    raise WorkCancelled("Selected card deck is no longer available.")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def review_receipt(self, owner, card_id, request_id):
        with self.engine.connect() as connection:
            receipt = connection.execute(
                text(
                    "SELECT quality_score,result_json FROM card_reviews WHERE student_id=:owner AND card_id=:card AND request_id=:request"
                ),
                {"owner": owner, "card": card_id, "request": request_id},
            ).first()
        return {"quality_score": receipt[0], "result": json.loads(receipt[1])} if receipt else None

    def quizzes(self, owner, limit, offset):
        with self.engine.connect() as connection:
            params = {"owner": owner, "limit": limit, "offset": offset}
            total = connection.execute(
                text("SELECT COUNT(*) FROM quizzes WHERE student_id=:owner"), params
            ).scalar()
            rows = [
                {**row, "provenance": json.loads(row["provenance"]) if row["provenance"] else None}
                for row in connection.execute(
                    text(
                        "SELECT quiz_id,session_id,title,created_at,revision,provenance_json AS provenance FROM quizzes WHERE student_id=:owner ORDER BY created_at DESC,quiz_id DESC LIMIT :limit OFFSET :offset"
                    ),
                    params,
                ).mappings()
            ]
        return {
            "quizzes": rows,
            "total": total,
            "next_offset": offset + len(rows) if offset + len(rows) < total else None,
        }

    def edit_card(self, owner, card_id, front, back):
        with self.engine.begin() as connection:
            result = connection.execute(
                text(
                    "UPDATE flashcards SET front_text=:front,back_text=:back,provenance_json=CASE WHEN provenance_json IS NULL THEN NULL ELSE json_set(provenance_json,'$.edited',json('true')) END WHERE card_id=:card AND student_id=:owner"
                ),
                {"owner": owner, "card": card_id, "front": front, "back": back},
            )
            return result.rowcount == 1

    @contextmanager
    def rating(self, owner, card_id, request_id, quality):
        with self.engine.begin() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            card = (
                connection.execute(
                    text("SELECT * FROM flashcards WHERE card_id=:card AND student_id=:owner"),
                    {"card": card_id, "owner": owner},
                )
                .mappings()
                .first()
            )
            if card is None:
                raise ValueError("Flashcard not found.")
            receipt = connection.execute(
                text(
                    "SELECT card_id,quality_score,result_json FROM card_reviews WHERE student_id=:owner AND request_id=:request"
                ),
                {"owner": owner, "request": request_id},
            ).first()
            if receipt and (receipt[0] != card_id or receipt[1] != quality):
                raise ReviewConflict("Review request ID was reused with different content.")
            yield connection, dict(card), json.loads(receipt[2]) if receipt else None

    def save_rating(self, connection, owner, card_id, request_id, quality, result):
        connection.execute(
            text("INSERT INTO card_reviews VALUES (:owner,:request,:card,:quality,:result,:now)"),
            {
                "owner": owner,
                "request": request_id,
                "card": card_id,
                "quality": quality,
                "result": json.dumps(result),
                "now": time.time(),
            },
        )
