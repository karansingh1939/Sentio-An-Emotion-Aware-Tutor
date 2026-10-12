import json
import logging
import os
from contextlib import nullcontext
from typing import List, Optional

from sentio.config import session_cfg
from sentio.session.models import Session

logger = logging.getLogger(__name__)


class SessionPersister:
    """
    Saves and loads Session summaries.
    Primary: SQLite via SQLAlchemy.
    Fallback: JSON files (no extra deps required).
    """

    def __init__(self):
        self._use_db = False
        self._engine = None
        self._json_dir = session_cfg.SESSION_LOG_PATH
        self._json_dir.mkdir(parents=True, exist_ok=True)
        self.auth_repo = None
        self.token_manager = None
        self.auth_service = None

    def load(self):
        """Try SQLAlchemy; fall back to JSON."""
        if self._use_db:
            return
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.pool import StaticPool

            pool_options = (
                {"poolclass": StaticPool}
                if session_cfg.DB_URL in ("sqlite://", "sqlite:///:memory:")
                else {}
            )
            self._engine = create_engine(
                session_cfg.DB_URL,
                connect_args={"check_same_thread": False},
                hide_parameters=True,
                **pool_options,
            )
            self._init_db()
            from sentio.persistence.migrations import apply_migrations

            apply_migrations(self._engine)
            self._use_db = True

            from sentio.auth.auth_service import AuthService
            from sentio.auth.repositories import AuthRepository
            from sentio.auth.token_manager import TokenManager
            from sentio.config import KNOWN_INSECURE_SECRETS, api_cfg

            env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development")).lower().strip()
            secret = getattr(api_cfg, "API_SECRET", "").strip()
            if env in ("prod", "production"):
                if not secret or secret in KNOWN_INSECURE_SECRETS or len(secret) < 16:
                    raise RuntimeError(
                        "CRITICAL SECURITY FAILURE: Insecure or missing TokenManager secret key in production mode."
                    )
            else:
                if not secret or secret in KNOWN_INSECURE_SECRETS:
                    from sentio.auth.local_secret import local_secret

                    secret = local_secret(session_cfg.DB_URL)

            self.token_manager = TokenManager(secret_key=secret)
            self.auth_repo = AuthRepository(self)
            self.auth_service = AuthService(self.auth_repo, self.token_manager)

            logger.info(f"Session persistence: SQLite ({session_cfg.DB_URL})")
        except ImportError:
            logger.warning(
                "SQLAlchemy not installed. Using JSON file persistence. Run: pip install sqlalchemy"
            )

    def _init_db(self):
        from sqlalchemy import text

        with self._engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            conn.execute(text("PRAGMA synchronous=NORMAL;"))
            conn.exec_driver_sql("BEGIN IMMEDIATE")
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS students (
                    student_id    TEXT PRIMARY KEY,
                    created_at    REAL NOT NULL,
                    metadata_json TEXT
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id   TEXT PRIMARY KEY,
                    student_id   TEXT NOT NULL,
                    subject      TEXT,
                    topic        TEXT,
                    difficulty   TEXT,
                    status       TEXT,
                    created_at   REAL,
                    closed_at    REAL,
                    duration_min REAL,
                    data_json    TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS emotion_events (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id   TEXT NOT NULL,
                    timestamp    REAL,
                    emotion      TEXT,
                    learning_state TEXT,
                    confidence   REAL,
                    strategy     TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS topics (
                    topic_id     TEXT PRIMARY KEY,
                    subject      TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    description  TEXT
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS topic_prerequisites (
                    parent_topic_id TEXT NOT NULL,
                    child_topic_id  TEXT NOT NULL,
                    PRIMARY KEY (parent_topic_id, child_topic_id),
                    FOREIGN KEY (parent_topic_id) REFERENCES topics(topic_id),
                    FOREIGN KEY (child_topic_id) REFERENCES topics(topic_id)
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS student_knowledge (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id          TEXT NOT NULL,
                    topic_id            TEXT NOT NULL,
                    mastery_score       REAL DEFAULT 0.0,
                    attempts_count      INTEGER DEFAULT 0,
                    consecutive_correct INTEGER DEFAULT 0,
                    last_attempt_at     REAL,
                    FOREIGN KEY (student_id) REFERENCES students(student_id),
                    FOREIGN KEY (topic_id) REFERENCES topics(topic_id)
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS flashcards (
                    card_id          TEXT PRIMARY KEY,
                    student_id       TEXT NOT NULL,
                    topic_id         TEXT NOT NULL,
                    front_text       TEXT NOT NULL,
                    back_text        TEXT NOT NULL,
                    created_at       REAL NOT NULL,
                    interval_days    INTEGER DEFAULT 0,
                    repetition_count INTEGER DEFAULT 0,
                    ease_factor      REAL DEFAULT 2.5,
                    next_review_at   REAL NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(student_id),
                    FOREIGN KEY (topic_id) REFERENCES topics(topic_id)
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS attention_logs (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id      TEXT NOT NULL,
                    timestamp       REAL NOT NULL,
                    emotion         TEXT NOT NULL,
                    attention_score REAL NOT NULL,
                    focused         INTEGER NOT NULL,
                    eye_openness    REAL,
                    head_pose_pitch REAL,
                    head_pose_yaw   REAL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_attention_logs_session_id ON attention_logs(session_id)"
                )
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS learning_goals (
                    goal_id       TEXT PRIMARY KEY,
                    student_id    TEXT NOT NULL,
                    topic_id      TEXT,
                    goal_text     TEXT NOT NULL,
                    target_date   REAL,
                    status        TEXT DEFAULT 'active',
                    created_at    REAL NOT NULL,
                    completed_at  REAL,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id          TEXT NOT NULL,
                    student_id          TEXT NOT NULL,
                    topic               TEXT NOT NULL,
                    question_text       TEXT NOT NULL,
                    student_answer      TEXT NOT NULL,
                    correct             INTEGER NOT NULL,
                    score               REAL,
                    response_time_sec   REAL,
                    difficulty          TEXT NOT NULL,
                    timestamp           REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)
            )

            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS documents (
                    id             TEXT PRIMARY KEY,
                    filename       TEXT NOT NULL,
                    file_type      TEXT NOT NULL,
                    category       TEXT NOT NULL,
                    subject        TEXT,
                    upload_date    REAL NOT NULL,
                    last_modified  REAL NOT NULL,
                    chunk_count    INTEGER DEFAULT 0,
                    embedding_count INTEGER DEFAULT 0,
                    status         TEXT NOT NULL,
                    last_indexed   REAL,
                    checksum       TEXT NOT NULL,
                    student_id     TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    chunk_id       TEXT PRIMARY KEY,
                    document_id    TEXT NOT NULL,
                    page_number    INTEGER,
                    chunk_index    INTEGER NOT NULL,
                    text_content   TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                )
            """)
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON document_chunks(document_id)")
            )

            document_columns = {
                row[1] for row in conn.execute(text("PRAGMA table_info(documents)"))
            }
            if "extraction_method" not in document_columns:
                conn.execute(
                    text("ALTER TABLE documents ADD COLUMN extraction_method TEXT DEFAULT 'text'")
                )

            if "student_id" not in document_columns:
                conn.execute(text("ALTER TABLE documents ADD COLUMN student_id TEXT"))
                conn.execute(
                    text("UPDATE documents SET student_id = 'stu_001' WHERE student_id IS NULL")
                )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_documents_student_id ON documents(student_id)")
            )

            session_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(sessions)"))}
            if "summary" not in session_columns:
                conn.execute(text("ALTER TABLE sessions ADD COLUMN summary TEXT"))

            # Phase D: Quiz, Flashcards & Whiteboards Schemas
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS quizzes (
                    quiz_id      TEXT PRIMARY KEY,
                    student_id   TEXT NOT NULL,
                    session_id   TEXT,
                    title        TEXT NOT NULL,
                    created_at   REAL NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(student_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS quiz_questions (
                    question_id    TEXT PRIMARY KEY,
                    quiz_id        TEXT NOT NULL,
                    question_text  TEXT NOT NULL,
                    question_type  TEXT NOT NULL,
                    options_json   TEXT,
                    correct_answer TEXT NOT NULL,
                    explanation    TEXT NOT NULL,
                    difficulty     TEXT NOT NULL,
                    topic          TEXT NOT NULL,
                    FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id) ON DELETE CASCADE
                )
            """)
            )
            quiz_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(quizzes)"))}
            if "submissions_json" not in quiz_columns:
                conn.execute(
                    text("ALTER TABLE quizzes ADD COLUMN submissions_json TEXT DEFAULT '{}'")
                )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS flashcard_decks (
                    deck_id      TEXT PRIMARY KEY,
                    student_id   TEXT NOT NULL,
                    deck_name    TEXT NOT NULL,
                    created_at   REAL NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS whiteboards (
                    whiteboard_id      TEXT PRIMARY KEY,
                    student_id         TEXT NOT NULL,
                    session_id         TEXT NOT NULL,
                    title              TEXT NOT NULL,
                    canvas_state_json  TEXT NOT NULL,
                    created_at         REAL NOT NULL,
                    updated_at         REAL NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(student_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            )

            card_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(flashcards)"))}
            if "deck_id" not in card_columns:
                conn.execute(
                    text(
                        "ALTER TABLE flashcards ADD COLUMN deck_id TEXT REFERENCES flashcard_decks(deck_id)"
                    )
                )
            if "tags" not in card_columns:
                conn.execute(text("ALTER TABLE flashcards ADD COLUMN tags TEXT"))

            # Identity & Privacy Platform tables
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS student_accounts (
                    student_id          TEXT PRIMARY KEY,
                    email               TEXT UNIQUE NOT NULL,
                    password_hash       TEXT NOT NULL,
                    role                TEXT NOT NULL DEFAULT 'student',
                    created_at          REAL NOT NULL,
                    consent_preferences TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    token_id            TEXT PRIMARY KEY,
                    student_id          TEXT NOT NULL,
                    token               TEXT UNIQUE NOT NULL,
                    expires_at          REAL NOT NULL,
                    created_at          REAL NOT NULL,
                    revoked             INTEGER DEFAULT 0,
                    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id          TEXT NOT NULL,
                    event_type          TEXT NOT NULL,
                    ip_address          TEXT,
                    timestamp           REAL NOT NULL,
                    details             TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS consent_history (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id          TEXT NOT NULL,
                    consent_version     TEXT NOT NULL,
                    preferences_json    TEXT NOT NULL,
                    timestamp           REAL NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
                )
            """)
            )

            conn.commit()

    def save_session(self, session: Session, connection=None):
        data = session.to_dict()
        if self._use_db:
            self._save_to_db(session, data, connection=connection)
        else:
            self._save_to_json(session.session_id, data)

    def _save_to_db(self, session: Session, data: dict, connection=None):
        from sqlalchemy import text

        with nullcontext(connection) if connection is not None else self._engine.connect() as conn:
            conn.execute(
                text("""
                INSERT OR REPLACE INTO sessions
                (session_id, student_id, subject, topic, difficulty, status,
                 created_at, closed_at, duration_min, data_json, summary)
                VALUES (:sid, :stud, :subj, :topic, :diff, :status,
                        :created, :closed, :dur, :data, :summary)
            """),
                {
                    "sid": session.session_id,
                    "stud": session.student_id,
                    "subj": session.subject,
                    "topic": session.topic,
                    "diff": session.difficulty,
                    "status": session.status.value,
                    "created": session.created_at,
                    "closed": session.closed_at,
                    "dur": round(session.duration_minutes, 2),
                    "data": json.dumps(data),
                    "summary": session.summary,
                },
            )
            if connection is None:
                conn.commit()

    def _save_to_json(self, session_id: str, data: dict):
        path = self._json_dir / f"{session_id}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_session_data(self, session_id: str) -> Optional[dict]:
        if self._use_db:
            return self._load_from_db(session_id)
        return self._load_from_json(session_id)

    def _load_from_db(self, session_id: str) -> Optional[dict]:
        from sqlalchemy import text

        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT data_json, summary FROM sessions WHERE session_id = :sid"),
                {"sid": session_id},
            ).fetchone()
        if row:
            data = json.loads(row[0])
            if row[1]:
                data["summary"] = row[1]
            return data
        return None

    def _load_from_json(self, session_id: str) -> Optional[dict]:
        path = self._json_dir / f"{session_id}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    def list_sessions(self, student_id: Optional[str] = None, limit: int = 50) -> List[dict]:
        """List recent sessions, optionally filtered by student."""
        if self._use_db:
            return self._list_from_db(student_id, limit)
        return self._list_from_json(student_id, limit)

    def session_page(self, owner, active_only=False, limit=50, offset=0):
        from sqlalchemy import text

        condition = "student_id=:owner" + (" AND status='active'" if active_only else "")
        with self._engine.connect() as connection:
            total = connection.execute(
                text(f"SELECT COUNT(*) FROM sessions WHERE {condition}"), {"owner": owner}
            ).scalar()
            rows = connection.execute(
                text(
                    f"SELECT data_json FROM sessions WHERE {condition} ORDER BY created_at DESC,session_id DESC LIMIT :limit OFFSET :offset"
                ),
                {"owner": owner, "limit": limit, "offset": offset},
            ).scalars()
            sessions = [json.loads(row) for row in rows]
        return {
            "sessions": sessions,
            "count": len(sessions),
            "total": total,
            "offset": offset,
            "next_offset": offset + len(sessions) if offset + len(sessions) < total else None,
        }

    def _list_from_db(self, student_id: Optional[str], limit: int) -> List[dict]:
        from sqlalchemy import text

        query = "SELECT data_json FROM sessions"
        params: dict = {}
        if student_id:
            query += " WHERE student_id = :stud"
            params["stud"] = student_id
        query += " ORDER BY created_at DESC LIMIT :lim"
        params["lim"] = limit

        with self._engine.connect() as conn:
            rows = conn.execute(text(query), params).fetchall()
        return [json.loads(r[0]) for r in rows]

    def _list_from_json(self, student_id: Optional[str], limit: int) -> List[dict]:
        files = sorted(
            self._json_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:limit]
        results = []
        for f in files:
            with open(f) as fp:
                data = json.load(fp)
            if student_id and data.get("student_id") != student_id:
                continue
            results.append(data)
        return results

    def register_document(self, doc: dict, connection=None) -> bool:
        if not self._use_db:
            return False
        from sqlalchemy import text

        try:
            doc_copy = dict(doc)
            doc_copy.setdefault("student_id", "stu_001")
            doc_copy.setdefault("extraction_method", "text")
            with (
                nullcontext(connection)
                if connection is not None
                else self._engine.connect() as conn
            ):
                conn.execute(
                    text("""
                    INSERT OR REPLACE INTO documents 
                    (id, filename, file_type, category, subject, upload_date, last_modified, chunk_count, embedding_count, status, last_indexed, checksum, student_id, extraction_method)
                    VALUES (:id, :filename, :file_type, :category, :subject, :upload_date, :last_modified, :chunk_count, :embedding_count, :status, :last_indexed, :checksum, :student_id, :extraction_method)
                """),
                    doc_copy,
                )
                if connection is None:
                    conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error registering document: {e}")
            return False

    def get_document_by_checksum(
        self, checksum: str, student_id: Optional[str] = None
    ) -> Optional[dict]:
        if not self._use_db:
            return None
        from sqlalchemy import text

        try:
            with self._engine.connect() as conn:
                query = """
                    SELECT id, filename, file_type, category, subject, upload_date, last_modified, chunk_count, embedding_count, status, last_indexed, checksum, student_id, extraction_method
                    FROM documents WHERE checksum = :checksum
                """
                params = {"checksum": checksum}
                if student_id:
                    query += " AND student_id = :sid"
                    params["sid"] = student_id
                row = conn.execute(text(query), params).fetchone()
                if row:
                    return dict(row._mapping)
            return None
        except Exception as e:
            logger.error(f"Error fetching document by checksum: {e}")
            return None

    def get_document_by_filename(
        self, filename: str, student_id: Optional[str] = None, category: Optional[str] = None
    ) -> Optional[dict]:
        if not self._use_db:
            return None
        from sqlalchemy import text

        try:
            with self._engine.connect() as conn:
                query = """
                    SELECT id, filename, file_type, category, subject, upload_date, last_modified, chunk_count, embedding_count, status, last_indexed, checksum, student_id, extraction_method
                    FROM documents WHERE filename = :filename
                """
                params = {"filename": filename}
                if student_id:
                    query += " AND student_id = :sid"
                    params["sid"] = student_id
                if category is not None:
                    query += " AND category = :category"
                    params["category"] = category
                row = conn.execute(text(query), params).fetchone()
                if row:
                    return dict(row._mapping)
            return None
        except Exception as e:
            logger.error(f"Error fetching document by filename: {e}")
            return None

    def delete_document(self, doc_id: str) -> bool:
        if not self._use_db:
            return False
        from sqlalchemy import text

        try:
            with self._engine.connect() as conn:
                conn.execute(text("DELETE FROM documents WHERE id = :id"), {"id": doc_id})
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return False

    def list_documents(self, student_id: Optional[str] = None) -> List[dict]:
        if not self._use_db:
            return []
        from sqlalchemy import text

        try:
            with self._engine.connect() as conn:
                query = """
                    SELECT id, filename, file_type, category, subject, upload_date, last_modified, chunk_count, embedding_count, status, last_indexed, checksum, student_id, extraction_method
                    FROM documents
                """
                params = {}
                if student_id:
                    query += " WHERE student_id = :sid"
                    params["sid"] = student_id
                rows = conn.execute(text(query), params).fetchall()
                return [dict(r._mapping) for r in rows]
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []

    def save_document_chunks(self, doc_id: str, chunks: List[dict], connection=None) -> bool:
        if not self._use_db:
            return False
        from sqlalchemy import text

        try:
            with (
                nullcontext(connection)
                if connection is not None
                else self._engine.connect() as conn
            ):
                conn.execute(
                    text("DELETE FROM document_chunks WHERE document_id = :doc_id"),
                    {"doc_id": doc_id},
                )
                for chunk in chunks:
                    conn.execute(
                        text("""
                        INSERT INTO document_chunks (chunk_id, document_id, page_number, chunk_index, text_content)
                        VALUES (:chunk_id, :document_id, :page_number, :chunk_index, :text_content)
                    """),
                        {
                            "chunk_id": chunk["chunk_id"],
                            "document_id": doc_id,
                            "page_number": chunk.get("page_number"),
                            "chunk_index": chunk["chunk_index"],
                            "text_content": chunk["text_content"],
                        },
                    )
                if connection is None:
                    conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving document chunks: {e}")
            return False

    def get_document_chunks(self, doc_id: str) -> List[dict]:
        if not self._use_db:
            return []
        from sqlalchemy import text

        try:
            with self._engine.connect() as conn:
                rows = conn.execute(
                    text("""
                    SELECT chunk_id, document_id, page_number, chunk_index, text_content
                    FROM document_chunks WHERE document_id = :doc_id ORDER BY chunk_index
                """),
                    {"doc_id": doc_id},
                ).fetchall()
                return [dict(r._mapping) for r in rows]
        except Exception as e:
            logger.error(f"Error getting document chunks: {e}")
            return []

    def get_all_chunks(self, student_id: Optional[str] = None) -> List[dict]:
        if not self._use_db:
            return []
        from sqlalchemy import text

        try:
            with self._engine.connect() as conn:
                query = """
                    SELECT c.chunk_id, c.document_id, c.page_number, c.chunk_index, c.text_content,
                           d.filename, d.category, d.subject, d.file_type
                    FROM document_chunks c
                    JOIN documents d ON c.document_id = d.id
                """
                params = {}
                if student_id:
                    query += " WHERE d.student_id = :sid"
                    params["sid"] = student_id
                rows = conn.execute(text(query), params).fetchall()
                return [dict(r._mapping) for r in rows]
        except Exception as e:
            logger.error(f"Error getting all chunks: {e}")
            return []

    def clear_all_documents_and_chunks(self) -> bool:
        if not self._use_db:
            return False
        from sqlalchemy import text

        try:
            with self._engine.connect() as conn:
                conn.execute(text("DELETE FROM document_chunks"))
                conn.execute(text("DELETE FROM documents"))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error clearing documents and chunks: {e}")
            return False
