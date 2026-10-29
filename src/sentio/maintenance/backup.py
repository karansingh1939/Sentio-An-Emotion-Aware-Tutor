"""Checksummed local snapshots. Keep snapshots private: they include secrets."""

import hashlib
import json
import shutil
import sqlite3
import time
from contextlib import ExitStack, closing
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory


def _digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _publish(staging, destination, attempts=8):
    """Move a verified staging folder into place, waiting out brief Windows file locks."""
    for attempt in range(attempts):
        try:
            return staging.rename(destination)
        except PermissionError:
            # Scanners and indexers briefly hold freshly written files on Windows.
            if attempt == attempts - 1:
                raise
            time.sleep(0.05 * 2**attempt)


def _safe_file(root, name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
        raise ValueError("Unsafe backup path")
    path = root.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError("Unsafe backup path")
    return path


def _sqlite_snapshot(source, destination):
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
        with closing(sqlite3.connect(destination)) as copied:
            original.backup(copied)
            if copied.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("SQLite integrity check failed")


def create_backup(home: Path, destination: Path) -> Path:
    """Snapshot a stopped local installation, holding Qdrant's exclusive lock."""
    import portalocker

    home, destination = Path(home).resolve(), Path(destination).resolve()
    if not home.is_dir() or destination.is_relative_to(home / "data"):
        raise ValueError("Use an existing home and a backup outside its data directory")
    if destination.exists():
        raise ValueError("Backup destination must not exist")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ExitStack() as locks:
        for lock_file in (home / "data").glob("**/.lock"):
            try:
                locks.enter_context(portalocker.Lock(lock_file, mode="r+", timeout=0))
            except portalocker.exceptions.LockException as exc:
                raise ValueError("Stop Sentio before backing up its data") from exc
        with TemporaryDirectory(dir=destination.parent, prefix="snapshot-") as temporary:
            staging = Path(temporary) / "payload"
            staging.mkdir()
            hashes = _copy_home(home, staging)
            manifest = {
                "version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "contains_private_data": True,
                "files": hashes,
            }
            (staging / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            verify_backup(staging)
            _publish(staging, destination)
    return destination


def _copy_home(home, staging):
    hashes = {}
    roots = ["data", "models", "prompts", "logs/sessions", "logs/emotions", ".env"]
    for name in roots:
        source = home / name
        candidates = sorted(source.rglob("*")) if source.is_dir() else [source]
        for original in candidates:
            if original.is_symlink():
                raise ValueError("Unsafe symbolic link in home")
            if not original.is_file() or original.name == ".lock":
                continue
            if original.name.endswith(("-wal", "-shm")):
                continue
            relative = original.relative_to(home).as_posix()
            copied = staging / relative
            copied.parent.mkdir(parents=True, exist_ok=True)
            if original.suffix in {".db", ".sqlite", ".sqlite3"}:
                _sqlite_snapshot(original, copied)
            else:
                shutil.copy2(original, copied)
            hashes[relative] = _digest(copied)
    return hashes


def verify_backup(snapshot: Path) -> int:
    snapshot = Path(snapshot).resolve()
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != 1 or not isinstance(manifest.get("files"), dict):
        raise ValueError("Unsupported backup manifest")
    for name, expected in manifest["files"].items():
        path = _safe_file(snapshot, name)
        if not path.is_file() or _digest(path) != expected:
            raise ValueError(f"Checksum mismatch: {name}")
    return len(manifest["files"])


def restore_backup(snapshot: Path, destination: Path) -> None:
    """Verify everything first; never merge a snapshot into an existing home."""
    snapshot, destination = Path(snapshot).resolve(), Path(destination).resolve()
    verify_backup(snapshot)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("Restore destination must be empty")
    if destination == snapshot or destination.is_relative_to(snapshot):
        raise ValueError("Restore destination must be outside the snapshot")
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    with TemporaryDirectory(dir=destination.parent, prefix="restore-") as temporary:
        staging = Path(temporary) / "payload"
        staging.mkdir()
        for name in manifest["files"]:
            original = _safe_file(snapshot, name)
            copied = _safe_file(staging, name)
            copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, copied)
        if destination.exists():
            destination.rmdir()
        _publish(staging, destination)
