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


def test_active_vector_store_blocks_snapshot(tmp_path):
    import portalocker

    home = tmp_path / "home"
    vector = home / "data/qdrant_db"
    vector.mkdir(parents=True)
    with portalocker.Lock(vector / ".lock", mode="a+", timeout=0):
        with pytest.raises(ValueError, match="Stop Sentio"):
            create_backup(home, tmp_path / "snapshot")
