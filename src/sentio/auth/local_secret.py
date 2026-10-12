"""Persistent local signing keys, published only after restricting access."""

import csv
import os
import re
import secrets
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


def restrict_access(path: Path):
    if os.name != "nt":
        path.chmod(0o600)
        return
    options = {
        "check": True,
        "capture_output": True,
        "text": True,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }
    identity = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], **options)
    sid = next(csv.reader(identity.stdout.strip().splitlines()))[-1]
    if not re.fullmatch(r"S-1-[0-9-]+", sid):
        raise RuntimeError("Cannot protect the local signing key")
    subprocess.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r", f"*{sid}:(F)", "*S-1-5-18:(F)"],
        **options,
    )


def local_secret(db_url: str) -> str:
    from sqlalchemy.engine import make_url

    database = make_url(db_url).database
    if not database or database == ":memory:":
        return secrets.token_urlsafe(48)
    target = Path(database).absolute().parent / ".sentio-secret"
    if not target.exists() and not target.is_symlink():
        with TemporaryDirectory(dir=target.parent, prefix="signing-key-") as temporary:
            staged = Path(temporary) / "key"
            with staged.open("x", encoding="ascii") as handle:
                handle.write(secrets.token_urlsafe(48))
                handle.flush()
                os.fsync(handle.fileno())
            restrict_access(staged)
            try:
                os.link(staged, target)
            except FileExistsError:
                pass  # Another startup published a complete protected key first.
    if target.is_symlink() or not target.is_file() or target.stat().st_size != 64:
        raise RuntimeError("Invalid local signing key; restore it from a private backup")
    restrict_access(target)
    value = target.read_text(encoding="ascii")
    if not re.fullmatch(r"[A-Za-z0-9_-]{64}", value):
        raise RuntimeError("Invalid local signing key; restore it from a private backup")
    return value
