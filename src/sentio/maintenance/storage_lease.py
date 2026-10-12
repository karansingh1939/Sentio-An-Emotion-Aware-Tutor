"""One application process owns persistent SQLite and document recovery."""

from contextlib import contextmanager
from pathlib import Path

import portalocker
from sqlalchemy.engine import make_url


@contextmanager
def storage_lease(db_url):
    url = make_url(db_url)
    if url.get_backend_name() != "sqlite":
        raise RuntimeError("This local release requires SQLite storage")
    if not url.database or url.database == ":memory:":
        yield
        return
    directory = Path(url.database).expanduser().resolve().parent
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ".lock"
    if path.is_symlink() or path.resolve() != path:
        raise RuntimeError("Unsafe storage ownership lock")
    lock = portalocker.Lock(path, mode="a+", timeout=0)
    try:
        lock.acquire()
    except portalocker.exceptions.LockException as exc:
        raise RuntimeError(
            "Sentio storage is already in use. Run one server process and stop it before backup."
        ) from exc
    try:
        yield
    finally:
        lock.release()
