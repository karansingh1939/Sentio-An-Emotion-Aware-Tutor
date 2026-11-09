"""A refused SQLite write lock is retried a few times, then reported."""

import sqlite3

import pytest
from sqlalchemy.exc import DatabaseError, OperationalError

from sentio.shared.sqlite_tx import begin_immediate


class FakeConnection:
    def __init__(self, refusals, error):
        self.refusals = refusals
        self.error = error
        self.begun = 0
        self.rollbacks = 0

    def exec_driver_sql(self, statement):
        assert statement == "BEGIN IMMEDIATE"
        if self.refusals:
            self.refusals -= 1
            raise self.error
        self.begun += 1

    def rollback(self):
        self.rollbacks += 1


@pytest.mark.parametrize(
    "error",
    [
        OperationalError("BEGIN", {}, sqlite3.OperationalError("database is locked")),
        # CI, WAL mode: a busy result reported with a stale message.
        DatabaseError("BEGIN", {}, sqlite3.DatabaseError("no more rows available")),
    ],
)
def test_a_briefly_refused_lock_is_retried(error):
    connection = FakeConnection(refusals=2, error=error)
    begin_immediate(connection, pause=0)
    assert connection.begun == 1 and connection.rollbacks == 2


def test_a_lock_that_stays_refused_is_reported():
    error = OperationalError("BEGIN", {}, sqlite3.OperationalError("database is locked"))
    connection = FakeConnection(refusals=10, error=error)
    with pytest.raises(OperationalError):
        begin_immediate(connection, attempts=3, pause=0)
    assert connection.begun == 0
