import pytest

from sentio.auth.local_secret import local_secret
from sentio.auth.token_manager import TokenManager
from sentio.maintenance.backup import create_backup, restore_backup


def test_key_survives_restart_and_private_restore(tmp_path):
    home = tmp_path / "home"
    (home / "data").mkdir(parents=True)
    url = "sqlite:///" + (home / "data/sentio.db").as_posix()
    first = TokenManager(local_secret(url))
    token = first.create_token({"student_id": "learner"}, 3600)
    assert TokenManager(local_secret(url)).verify_token(token)["student_id"] == "learner"
    snapshot = create_backup(home, tmp_path / "backup")
    restored = tmp_path / "restored"
    restore_backup(snapshot, restored)
    restored_url = "sqlite:///" + (restored / "data/sentio.db").as_posix()
    assert TokenManager(local_secret(restored_url)).verify_token(token)["student_id"] == "learner"


def test_invalid_key_is_never_silently_replaced(tmp_path):
    key = tmp_path / ".sentio-secret"
    key.write_text("broken", encoding="ascii")
    with pytest.raises(RuntimeError, match="restore"):
        local_secret("sqlite:///" + (tmp_path / "sentio.db").as_posix())
    assert key.read_text() == "broken"
