"""Shared SQLite state remains available across API threads and reloads."""

from sentio.config import session_cfg
from sentio.session.manager import SessionManager


def test_memory_database_is_shared_across_threads(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setattr(session_cfg, "DB_URL", "sqlite:///:memory:")
    manager = SessionManager()
    manager.load()
    session = manager.create_session("owner", "physics", "mechanics")
    with ThreadPoolExecutor(max_workers=1) as executor:
        students = executor.submit(manager.persister.load_session_data, session.session_id).result()
    assert students is not None
    manager.persister._engine.dispose()


def test_reloading_manager_preserves_in_memory_data(monkeypatch):
    monkeypatch.setattr(session_cfg, "DB_URL", "sqlite:///:memory:")
    manager = SessionManager()
    manager.load()
    session = manager.create_session("owner", "physics", "mechanics")
    manager.load()
    assert manager.persister.load_session_data(session.session_id) is not None
    manager.persister._engine.dispose()
