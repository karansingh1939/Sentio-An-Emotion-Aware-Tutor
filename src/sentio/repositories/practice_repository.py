"""Saved practice access and atomic card review receipts."""

import json
import time
from contextlib import contextmanager

from sqlalchemy import text


class ReviewConflict(ValueError):
    pass


class PracticeRepository:
    def __init__(self, engine):
        self.engine = engine

    def quizzes(self, owner, limit, offset):
        with self.engine.connect() as connection:
            params = {"owner": owner, "limit": limit, "offset": offset}
            total = connection.execute(
                text("SELECT COUNT(*) FROM quizzes WHERE student_id=:owner"), params
            ).scalar()
            rows = [
                dict(row)
                for row in connection.execute(
                    text(
                        "SELECT quiz_id,session_id,title,created_at FROM quizzes WHERE student_id=:owner ORDER BY created_at DESC,quiz_id DESC LIMIT :limit OFFSET :offset"
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
                    "UPDATE flashcards SET front_text=:front,back_text=:back WHERE card_id=:card AND student_id=:owner"
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
