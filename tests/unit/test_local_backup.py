"""Backups restore verified local state without overwriting existing homes."""

import json
import sqlite3

import pytest

from sentio.maintenance.backup import create_backup, restore_backup, verify_backup


def test_backup_restores_sqlite_documents_and_private_configuration(tmp_path):
    home = tmp_path / "home"
    (home / "data/documents").mkdir(parents=True)
    (home / "data/documents/notes.txt").write_text("Owned notes", encoding="utf-8")
    (home / ".env").write_text("API_SECRET=test-only", encoding="utf-8")
    with sqlite3.connect(home / "data/tutor_sessions.db") as db:
        db.execute("CREATE TABLE sample (value TEXT)")
        db.execute("INSERT INTO sample VALUES ('preserved')")
    snapshot = create_backup(home, tmp_path / "snapshot")
    assert verify_backup(snapshot) == 3
    restored = tmp_path / "restored"
    restore_backup(snapshot, restored)
    assert (restored / "data/documents/notes.txt").read_text() == "Owned notes"
    assert (restored / ".env").read_text() == "API_SECRET=test-only"
    with sqlite3.connect(restored / "data/tutor_sessions.db") as db:
        assert db.execute("SELECT value FROM sample").fetchone()[0] == "preserved"
    with pytest.raises(ValueError, match="empty"):
        restore_backup(snapshot, restored)


def test_corruption_and_escaping_manifest_are_rejected_before_restore(tmp_path):
    home = tmp_path / "home"
    (home / "data").mkdir(parents=True)
    (home / "data/example.txt").write_text("original")
    snapshot = create_backup(home, tmp_path / "snapshot")
    (snapshot / "data/example.txt").write_text("changed")
    with pytest.raises(ValueError, match="Checksum"):
        restore_backup(snapshot, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()
    manifest = json.loads((snapshot / "manifest.json").read_text())
    manifest["files"] = {"../outside.txt": "invalid"}
    (snapshot / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Unsafe"):
        verify_backup(snapshot)


def _sample_home(tmp_path):
    home = tmp_path / "home"
    (home / "data").mkdir(parents=True)
    (home / "data/example.txt").write_text("original")
    return home


def _lock_first_renames(monkeypatch, count):
    """Windows briefly denies renaming freshly written folders while scanners hold them."""
    from pathlib import Path

    from sentio.maintenance import backup

    attempts = []
    original = Path.rename

    def locked_rename(self, target):
        attempts.append(target)
        if len(attempts) <= count:
            raise PermissionError(5, "Access is denied")
        return original(self, target)

    monkeypatch.setattr(Path, "rename", locked_rename)
    monkeypatch.setattr(backup.time, "sleep", lambda seconds: None)
    return attempts


def test_transient_rename_lock_is_retried_for_backup_and_restore(tmp_path, monkeypatch):
    home = _sample_home(tmp_path)
    attempts = _lock_first_renames(monkeypatch, 2)
    snapshot = create_backup(home, tmp_path / "snapshot")
    assert len(attempts) >= 3  # A real Windows lock may add attempts.
    assert verify_backup(snapshot) == 1
    attempts.clear()
    restore_backup(snapshot, tmp_path / "restored")
    assert len(attempts) >= 3  # A real Windows lock may add attempts.
    assert (tmp_path / "restored/data/example.txt").read_text() == "original"


def test_persistent_rename_lock_fails_without_partial_snapshot(tmp_path, monkeypatch):
    home = _sample_home(tmp_path)
    _lock_first_renames(monkeypatch, 1000)
    with pytest.raises(PermissionError):
        create_backup(home, tmp_path / "snapshot")
    assert not (tmp_path / "snapshot").exists()
    assert not list(tmp_path.glob("snapshot-*"))


def test_active_vector_store_blocks_snapshot(tmp_path):
    import portalocker

    home = tmp_path / "home"
    vector = home / "data/qdrant_db"
    vector.mkdir(parents=True)
    with portalocker.Lock(vector / ".lock", mode="a+", timeout=0):
        with pytest.raises(ValueError, match="Stop Sentio"):
            create_backup(home, tmp_path / "snapshot")
