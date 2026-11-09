"""Keep grading progress and replayable results in one SQLite transaction."""

import json
from contextlib import contextmanager

from sqlalchemy import text

from sentio.shared.sqlite_tx import begin_immediate


class RevisionConflict(ValueError):
    pass


class QuizRepository:
    def __init__(self, persister):
        self.persister = persister

    @contextmanager
    def submission(self, quiz_id):
        with self.persister._engine.connect() as connection:
            begin_immediate(connection)
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

    def edit_question(self, owner, quiz_id, question_id, fields, expected_revision=None):
        """Apply a validated edit and bump the quiz revision; None when not owned or absent."""
        with self.persister._engine.connect() as connection:
            begin_immediate(connection)
            try:
                quiz = connection.execute(
                    text(
                        "SELECT revision,provenance_json FROM quizzes WHERE quiz_id=:quiz AND student_id=:owner"
                    ),
                    {"quiz": quiz_id, "owner": owner},
                ).first()
                found = (
                    quiz
                    and connection.execute(
                        text(
                            "SELECT 1 FROM quiz_questions WHERE quiz_id=:quiz AND question_id=:question"
                        ),
                        {"quiz": quiz_id, "question": question_id},
                    ).first()
                )
                if not found:
                    connection.rollback()
                    return None
                revision = quiz[0] or 0
                if expected_revision is not None and expected_revision != revision:
                    raise RevisionConflict(
                        "This quiz changed since you opened it. Reload it and try again."
                    )
                connection.execute(
                    text(
                        "UPDATE quiz_questions SET question_text=:question_text,options_json=:options,correct_answer=:correct_answer,explanation=:explanation WHERE question_id=:question"
                    ),
                    {
                        **fields,
                        "options": json.dumps(fields["options"]) if fields["options"] else None,
                        "question": question_id,
                    },
                )
                provenance = json.loads(quiz[1]) if quiz[1] else None
                if provenance is not None:
                    provenance["edited"] = True
                connection.execute(
                    text(
                        "UPDATE quizzes SET revision=:revision,provenance_json=:provenance WHERE quiz_id=:quiz"
                    ),
                    {
                        "revision": revision + 1,
                        "provenance": json.dumps(provenance) if provenance else None,
                        "quiz": quiz_id,
                    },
                )
                connection.commit()
                return revision + 1
            except Exception:
                connection.rollback()
                raise
