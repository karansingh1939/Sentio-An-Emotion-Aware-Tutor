import pytest
from sqlalchemy import create_engine, event, text

from sentio.repositories.sessions import SessionPersister


def test_interrupted_fresh_schema_rolls_back_instead_of_leaving_partial_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    persister = SessionPersister()
    persister._engine = engine

    def fail(connection, cursor, statement, parameters, context, executemany):
        if "CREATE TABLE IF NOT EXISTS quizzes" in statement:
            raise RuntimeError("Interrupted schema write")

    event.listen(engine, "before_cursor_execute", fail)
    with pytest.raises(RuntimeError, match="Interrupted"):
        persister._init_db()
    event.remove(engine, "before_cursor_execute", fail)
    with engine.connect() as connection:
        assert not connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).all()
    persister._init_db()
    engine.dispose()


def test_legacy_column_upgrade_rolls_back_and_then_preserves_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    persister = SessionPersister()
    persister._engine = engine
    with engine.begin() as connection:
        connection.execute(
            text("""CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY, student_id TEXT, subject TEXT, topic TEXT,
            difficulty TEXT, status TEXT, created_at REAL, closed_at REAL,
            duration_min REAL, data_json TEXT)""")
        )
        connection.execute(
            text("INSERT INTO sessions (session_id,data_json) VALUES ('saved','preserve-me')")
        )

    def fail(connection, cursor, statement, parameters, context, executemany):
        if "CREATE TABLE IF NOT EXISTS whiteboards" in statement:
            raise RuntimeError("Interrupted upgrade")

    event.listen(engine, "before_cursor_execute", fail)
    with pytest.raises(RuntimeError, match="Interrupted"):
        persister._init_db()
    event.remove(engine, "before_cursor_execute", fail)
    with engine.connect() as connection:
        assert "summary" not in {
            row[1] for row in connection.execute(text("PRAGMA table_info(sessions)"))
        }
        assert (
            connection.execute(
                text("SELECT data_json FROM sessions WHERE session_id='saved'")
            ).scalar()
            == "preserve-me"
        )
    persister._init_db()
    persister._init_db()
    with engine.connect() as connection:
        assert "summary" in {
            row[1] for row in connection.execute(text("PRAGMA table_info(sessions)"))
        }
        assert (
            connection.execute(
                text("SELECT data_json FROM sessions WHERE session_id='saved'")
            ).scalar()
            == "preserve-me"
        )
    engine.dispose()
