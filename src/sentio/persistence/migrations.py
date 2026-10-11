"""Additive SQLite migrations, versioned and committed together."""

import time

from sqlalchemy import text

MIGRATIONS = {
    1: [
        """CREATE TABLE jobs (
            job_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, kind TEXT NOT NULL,
            lane TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
            created_at REAL NOT NULL, updated_at REAL NOT NULL,
            result_json TEXT, error TEXT)""",
        "CREATE INDEX idx_jobs_owner ON jobs(student_id, created_at)",
        """CREATE TABLE chat_requests (
            session_id TEXT NOT NULL, request_id TEXT NOT NULL, student_id TEXT NOT NULL,
            fingerprint TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT,
            updated_at REAL NOT NULL, PRIMARY KEY(session_id, request_id))""",
        """CREATE TABLE recovery_operations (
            operation_id TEXT PRIMARY KEY, student_id TEXT NOT NULL,
            kind TEXT NOT NULL, payload_json TEXT NOT NULL,
            status TEXT NOT NULL, created_at REAL NOT NULL, error TEXT)""",
    ],
    2: [
        "ALTER TABLE chat_requests ADD COLUMN message TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE chat_requests ADD COLUMN context TEXT NOT NULL DEFAULT ''",
    ],
    3: [
        """CREATE TABLE study_preferences (
            student_id TEXT PRIMARY KEY, daily_minutes INTEGER NOT NULL DEFAULT 30,
            updated_at REAL NOT NULL)""",
        """CREATE TABLE daily_plans (
            student_id TEXT NOT NULL, day TEXT NOT NULL, budget_minutes INTEGER NOT NULL,
            tasks_json TEXT NOT NULL, created_at REAL NOT NULL,
            PRIMARY KEY(student_id, day))""",
    ],
    4: [
        """CREATE TABLE card_reviews (
            student_id TEXT NOT NULL, request_id TEXT NOT NULL, card_id TEXT NOT NULL,
            quality_score INTEGER NOT NULL, result_json TEXT NOT NULL, created_at REAL NOT NULL,
            PRIMARY KEY(student_id, request_id))""",
    ],
}


def apply_migrations(engine):
    with engine.begin() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at REAL NOT NULL)"
            )
        )
        completed = set(connection.execute(text("SELECT version FROM schema_migrations")).scalars())
        for version, statements in sorted(MIGRATIONS.items()):
            if version in completed:
                continue
            for statement in statements:
                connection.execute(text(statement))
            connection.execute(
                text("INSERT INTO schema_migrations VALUES (:version, :time)"),
                {"version": version, "time": time.time()},
            )
