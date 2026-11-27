import logging
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from sentio.auth.models import AuditLog, ConsentHistory, RefreshToken, UserAccount

logger = logging.getLogger(__name__)


def _existing_tables(connection):
    return set(
        connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars()
    )


def account_exists(connection, student_id):
    """Whether the account still exists, read on the caller's connection and transaction."""
    return (
        connection.execute(
            text("SELECT student_id FROM student_accounts WHERE student_id=:owner"),
            {"owner": student_id},
        ).first()
        is not None
    )


class AuthRepository:
    """SQL persistence layer for all authentication and privacy entities."""

    def __init__(self, persister: Any):
        self.persister = persister

    def _execute(self, query: str, params: Dict[str, Any] = None) -> Any:
        with self.persister.engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            conn.commit()
            return result

    def save_account(self, account: UserAccount):
        """Saves a student account to SQLite."""
        # Ensure student base record exists first
        self._execute(
            "INSERT OR IGNORE INTO students (student_id, created_at, metadata_json) VALUES (:sid, :created, '{}')",
            {"sid": account.student_id, "created": account.created_at},
        )

        self._execute(
            "INSERT INTO student_accounts (student_id, email, password_hash, role, created_at, consent_preferences, token_version) "
            "VALUES (:sid, :email, :pwd, :role, :created, :consent, :version) "
            "ON CONFLICT(student_id) DO UPDATE SET email=excluded.email, password_hash=excluded.password_hash, "
            "role=excluded.role, consent_preferences=excluded.consent_preferences, token_version=excluded.token_version",
            {
                "sid": account.student_id,
                "email": account.email,
                "pwd": account.password_hash,
                "role": account.role,
                "created": account.created_at,
                "consent": account.consent_preferences,
                "version": account.token_version,
            },
        )

    def upgrade_password_hash(self, owner, previous_hash, replacement):
        result = self._execute(
            "UPDATE student_accounts SET password_hash=:replacement WHERE student_id=:owner AND password_hash=:previous",
            {"owner": owner, "previous": previous_hash, "replacement": replacement},
        )
        return result.rowcount == 1

    def get_account_by_email(self, email: str) -> Optional[UserAccount]:
        """Looks up an account by login email."""
        res = self._execute(
            "SELECT student_id, email, password_hash, role, created_at, consent_preferences, token_version "
            "FROM student_accounts WHERE email = :email",
            {"email": email},
        )
        if not res:
            return None
        row = res.fetchone()
        if not row:
            return None
        return UserAccount(*row)

    def get_account_by_student_id(self, student_id: str) -> Optional[UserAccount]:
        """Looks up an account by unique student ID."""
        res = self._execute(
            "SELECT student_id, email, password_hash, role, created_at, consent_preferences, token_version "
            "FROM student_accounts WHERE student_id = :sid",
            {"sid": student_id},
        )
        if not res:
            return None
        row = res.fetchone()
        if not row:
            return None
        return UserAccount(*row)

    def delete_account(self, student_id: str, connection=None):
        """Delete the complete owned SQL inventory atomically."""
        params = {"sid": student_id}
        dependent_tables = {
            "document_chunks": "document_id IN (SELECT id FROM documents WHERE student_id = :sid)",
            "quiz_questions": "quiz_id IN (SELECT quiz_id FROM quizzes WHERE student_id = :sid)",
            "attention_logs": "session_id IN (SELECT session_id FROM sessions WHERE student_id = :sid)",
            "emotion_events": "session_id IN (SELECT session_id FROM sessions WHERE student_id = :sid)",
        }
        owned_tables = [
            "study_preferences",
            "daily_plans",
            "card_reviews",
            "job_requests",
            "jobs",
            "chat_requests",
            "recovery_operations",
            "refresh_tokens",
            "audit_logs",
            "consent_history",
            "student_knowledge",
            "flashcards",
            "flashcard_decks",
            "learning_goals",
            "quiz_attempts",
            "quizzes",
            "whiteboards",
            "note_topics",
            "syllabus_items",
            "documents",
            "courses",
            "sessions",
            "student_accounts",
            "students",
        ]
        from contextlib import nullcontext

        with (
            nullcontext(connection)
            if connection is not None
            else self.persister.engine.begin() as connection
        ):
            # Legacy tables such as whiteboards exist only in older databases.
            existing = _existing_tables(connection)
            for table, condition in dependent_tables.items():
                if table in existing:
                    connection.execute(text(f"DELETE FROM {table} WHERE {condition}"), params)
            for table in owned_tables:
                if table in existing:
                    connection.execute(text(f"DELETE FROM {table} WHERE student_id = :sid"), params)

    def export_profile(self, student_id):
        """The account, sessions, knowledge, cards, attempts and goals, in the export's columns."""
        queries = {
            "account": "SELECT student_id, email, role, created_at FROM student_accounts WHERE student_id = :sid",
            "sessions": "SELECT session_id, subject, topic, difficulty, status, created_at, closed_at, duration_min, summary FROM sessions WHERE student_id = :sid",
            "student_knowledge": "SELECT topic_id, mastery_score, attempts_count, consecutive_correct, last_attempt_at FROM student_knowledge WHERE student_id = :sid",
            "flashcards": "SELECT card_id, topic_id, front_text, back_text, created_at, interval_days, repetition_count, ease_factor, stability, difficulty, last_review_at, next_review_at FROM flashcards WHERE student_id = :sid",
            "quiz_attempts": "SELECT id, session_id, topic, question_text, student_answer, correct, score, response_time_sec, difficulty, timestamp FROM quiz_attempts WHERE student_id = :sid",
            "learning_goals": "SELECT goal_id, topic_id, goal_text, target_date, status, created_at, completed_at FROM learning_goals WHERE student_id = :sid",
        }
        with self.persister.engine.connect() as connection:
            return {
                name: connection.execute(text(query), {"sid": student_id}).mappings().all()
                for name, query in queries.items()
            }

    def export_study_artifacts(self, student_id):
        inventory = {
            "study_preferences": "student_id = :sid",
            "daily_plans": "student_id = :sid",
            "card_reviews": "student_id = :sid",
            "job_requests": "student_id = :sid",
            "jobs": "student_id = :sid",
            "chat_requests": "student_id = :sid",
            "courses": "student_id = :sid",
            "note_topics": "student_id = :sid",
            "syllabus_items": "student_id = :sid",
            "documents": "student_id = :sid",
            "document_chunks": "document_id IN (SELECT id FROM documents WHERE student_id = :sid)",
            "quizzes": "student_id = :sid",
            "quiz_questions": "quiz_id IN (SELECT quiz_id FROM quizzes WHERE student_id = :sid)",
            "flashcard_decks": "student_id = :sid",
            "whiteboards": "student_id = :sid",
            "attention_logs": "session_id IN (SELECT session_id FROM sessions WHERE student_id = :sid)",
            "emotion_events": "session_id IN (SELECT session_id FROM sessions WHERE student_id = :sid)",
        }
        with self.persister.engine.connect() as connection:
            existing = _existing_tables(connection)
            return {
                table: [
                    dict(row)
                    for row in connection.execute(
                        text(f"SELECT * FROM {table} WHERE {condition}"), {"sid": student_id}
                    ).mappings()
                ]
                for table, condition in inventory.items()
                if table in existing
            }

    def delete_telemetry(self, student_id: str):
        """Purges only webcam-attention and emotion events telemetry."""
        with self.persister.engine.connect() as conn:
            sessions_res = conn.execute(
                text("SELECT session_id FROM sessions WHERE student_id = :sid"), {"sid": student_id}
            ).fetchall()
            for s in sessions_res:
                conn.execute(
                    text("DELETE FROM attention_logs WHERE session_id = :sid"), {"sid": s[0]}
                )
                conn.execute(
                    text("DELETE FROM emotion_events WHERE session_id = :sid"), {"sid": s[0]}
                )
            conn.commit()

    def save_refresh_token(self, token: RefreshToken):
        self._execute(
            "INSERT OR REPLACE INTO refresh_tokens (token_id, student_id, token, expires_at, created_at, revoked) "
            "VALUES (:tid, :sid, :tok, :exp, :created, :revoked)",
            {
                "tid": token.token_id,
                "sid": token.student_id,
                "tok": token.token,
                "exp": token.expires_at,
                "created": token.created_at,
                "revoked": token.revoked,
            },
        )

    def get_refresh_token(self, token_str: str) -> Optional[RefreshToken]:
        res = self._execute(
            "SELECT token_id, student_id, token, expires_at, created_at, revoked "
            "FROM refresh_tokens WHERE token = :tok",
            {"tok": token_str},
        )
        if not res:
            return None
        row = res.fetchone()
        if not row:
            return None
        return RefreshToken(*row)

    def revoke_refresh_token(self, token_id: str):
        self._execute(
            "UPDATE refresh_tokens SET revoked = 1 WHERE token_id = :tid", {"tid": token_id}
        )

    def save_audit_log(self, audit: AuditLog):
        self._execute(
            "INSERT INTO audit_logs (student_id, event_type, ip_address, timestamp, details) "
            "VALUES (:sid, :event, :ip, :timestamp, :details)",
            {
                "sid": audit.student_id,
                "event": audit.event_type,
                "ip": audit.ip_address,
                "timestamp": audit.timestamp or time.time(),
                "details": audit.details,
            },
        )

    def get_audit_logs(self, student_id: str) -> List[dict]:
        res = self._execute(
            "SELECT event_type, ip_address, timestamp, details FROM audit_logs WHERE student_id = :sid ORDER BY timestamp DESC",
            {"sid": student_id},
        )
        if not res:
            return []
        return [
            {"event_type": r[0], "ip_address": r[1], "timestamp": r[2], "details": r[3]}
            for r in res.fetchall()
        ]

    def save_consent(self, consent: ConsentHistory):
        self._execute(
            "INSERT INTO consent_history (student_id, consent_version, preferences_json, timestamp) "
            "VALUES (:sid, :ver, :pref, :timestamp)",
            {
                "sid": consent.student_id,
                "ver": consent.consent_version,
                "pref": consent.preferences_json,
                "timestamp": consent.timestamp,
            },
        )

    def get_consent_history(self, student_id: str) -> List[dict]:
        res = self._execute(
            "SELECT consent_version, preferences_json, timestamp FROM consent_history WHERE student_id = :sid ORDER BY timestamp DESC",
            {"sid": student_id},
        )
        if not res:
            return []
        return [
            {"consent_version": r[0], "preferences_json": r[1], "timestamp": r[2]}
            for r in res.fetchall()
        ]
