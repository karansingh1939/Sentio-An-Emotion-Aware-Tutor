"""Keep grading progress and replayable results in one SQLite transaction."""

import json
from contextlib import contextmanager

from sqlalchemy import text


class QuizRepository:
    def __init__(self, persister):
        self.persister = persister

    @contextmanager
    def submission(self, quiz_id):
        with self.persister._engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            row = connection.execute(
                text("SELECT submissions_json FROM quizzes WHERE quiz_id = :id"), {"id": quiz_id}
            ).scalar_one()
            try:
                yield connection, json.loads(row or "{}")
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def save_results(self, connection, quiz_id, results):
        connection.execute(
            text("UPDATE quizzes SET submissions_json = :results WHERE quiz_id = :id"),
            {"id": quiz_id, "results": json.dumps(results)},
        )
