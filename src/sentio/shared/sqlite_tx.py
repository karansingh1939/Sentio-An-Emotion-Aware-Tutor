"""Start SQLite write transactions that survive brief contention.

Background jobs and requests write to the same SQLite file. `BEGIN IMMEDIATE` takes the
write lock up front, and SQLite can refuse it for a moment: on CI it failed as "database
is locked" and, in WAL mode, as "no more rows available" (a busy result reported with a
stale message). A refused BEGIN starts no transaction, so trying again is safe.
"""

import logging
import time

from sqlalchemy.exc import DBAPIError

logger = logging.getLogger(__name__)

ATTEMPTS = 5


def begin_immediate(connection, attempts=ATTEMPTS, pause=0.2):
    """Run BEGIN IMMEDIATE on `connection`, retrying a refused lock a few times."""
    for attempt in range(1, attempts + 1):
        try:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            return
        except DBAPIError as error:
            if attempt == attempts:
                raise
            logger.warning(
                "SQLite write lock refused (%s); retrying %d/%d",
                str(error.orig).splitlines()[0],
                attempt,
                attempts - 1,
            )
            try:
                connection.rollback()  # clear SQLAlchemy's view of a half-started transaction
            except DBAPIError:
                pass
            time.sleep(pause * attempt)
