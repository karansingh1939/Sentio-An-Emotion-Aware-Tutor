import pytest

from sentio.maintenance.backup import create_backup
from sentio.maintenance.storage_lease import storage_lease


def test_second_owner_and_backup_are_refused_until_application_stops(tmp_path):
    home = tmp_path / "home"
    (home / "data").mkdir(parents=True)
    url = "sqlite:///" + (home / "data/sentio.db").as_posix()
    with storage_lease(url):
        with pytest.raises(RuntimeError, match="already in use"):
            with storage_lease(url):
                pytest.fail("Two processes cannot own the same persistent data")
        with pytest.raises(ValueError, match="Stop Sentio"):
            create_backup(home, tmp_path / "must-not-exist")
    snapshot = create_backup(home, tmp_path / "stopped-backup")
    assert (snapshot / "manifest.json").exists()
    assert not (snapshot / "data/.lock").exists()
