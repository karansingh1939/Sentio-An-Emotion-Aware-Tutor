"""Commit account deletion before recoverable cleanup of owned files and vectors."""

import json
import logging
import re
import shutil
import time
from pathlib import Path

from sqlalchemy import text

logger = logging.getLogger(__name__)


class AccountCleanup:
    def __init__(self, persister, vectors, document_root, session_logs, emotion_logs):
        self.persister = persister
        self.engine = persister._engine
        self.vectors = vectors
        self.root = Path(document_root).resolve()
        self.session_logs = Path(session_logs).resolve()
        self.emotion_logs = Path(emotion_logs).resolve()

    def delete(self, owner):
        with self.engine.begin() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            parameters = {"owner": owner}
            documents = list(
                connection.execute(
                    text("SELECT id FROM documents WHERE student_id=:owner"), parameters
                ).scalars()
            )
            sessions = list(
                connection.execute(
                    text("SELECT session_id FROM sessions WHERE student_id=:owner"), parameters
                ).scalars()
            )
            self.owned_directory(owner)  # Validate before the destructive transaction.
            for session_id in sessions:
                self.log_path(self.session_logs, session_id, ".json")
            connection.execute(
                text("INSERT INTO account_cleanup VALUES (:owner,:documents,:sessions,:now)"),
                {
                    "owner": owner,
                    "documents": json.dumps(documents),
                    "sessions": json.dumps(sessions),
                    "now": time.time(),
                },
            )
            self.persister.auth_repo.delete_account(owner, connection=connection)
        complete = self.cleanup(owner, documents, sessions)
        return {"cleanup_pending": not complete, "session_ids": sessions}

    def owned_directory(self, owner):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", owner):
            raise ValueError("Invalid account cleanup identity")
        candidate = self.root / owner
        if candidate.is_symlink() or candidate.resolve() != candidate or candidate == self.root:
            raise ValueError("Unsafe account cleanup directory")
        return candidate

    @staticmethod
    def log_path(root, session_id, suffix):
        if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", session_id):
            raise ValueError("Invalid session cleanup identity")
        path = root / (session_id + suffix)
        if path.is_symlink() or path.resolve() != path:
            raise ValueError("Unsafe session cleanup path")
        return path

    def cleanup(self, owner, documents, sessions):
        try:
            with self.engine.connect() as connection:
                if connection.execute(
                    text("SELECT 1 FROM student_accounts WHERE student_id=:owner"), {"owner": owner}
                ).scalar():
                    raise ValueError("Account cleanup cannot remove an active learner's files")
                active_documents = set(
                    connection.execute(text("SELECT id FROM documents")).scalars()
                )
                active_sessions = set(
                    connection.execute(text("SELECT session_id FROM sessions")).scalars()
                )
            owned = self.owned_directory(owner)
            if owned.exists():
                shutil.rmtree(owned)
            for document_id in documents:
                if document_id not in active_documents:
                    if self.vectors.delete_document_points(document_id) is False:
                        raise RuntimeError("Vector cleanup is pending")
            for session_id in sessions:
                if session_id in active_sessions:
                    continue
                self.log_path(self.session_logs, session_id, ".json").unlink(missing_ok=True)
                self.log_path(self.emotion_logs, session_id, "_emotions.json").unlink(
                    missing_ok=True
                )
            with self.engine.begin() as connection:
                connection.execute(
                    text("DELETE FROM account_cleanup WHERE student_id=:owner"), {"owner": owner}
                )
            return True
        except Exception:
            logger.warning("Account file/vector cleanup remains pending")
            return False

    def recover(self):
        with self.engine.connect() as connection:
            pending = list(connection.execute(text("SELECT * FROM account_cleanup")).mappings())
        for row in pending:
            try:
                documents = json.loads(row["document_ids_json"])
                sessions = json.loads(row["session_ids_json"])
                if not isinstance(documents, list) or not all(
                    isinstance(value, str) for value in documents
                ):
                    raise ValueError("Invalid document cleanup inventory")
                if not isinstance(sessions, list) or not all(
                    isinstance(value, str) for value in sessions
                ):
                    raise ValueError("Invalid session cleanup inventory")
                self.cleanup(row["student_id"], documents, sessions)
            except (ValueError, TypeError):
                logger.warning("Invalid account cleanup record retained for diagnostics")
