"""Cancellation and publication barriers shared by jobs and model requests."""

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Event, RLock

_context = ContextVar("sentio_work", default=None)


class WorkCancelled(Exception):
    pass


class WorkInputError(ValueError):
    """A deliberately safe, actionable message for an owner-scoped job."""


class WorkControl:
    def __init__(self, progress=None, emit=None):
        self.cancelled = Event()
        self.lock = RLock()
        self.committed = False
        self.response = None
        self.progress = progress or (lambda stage: None)
        self.emit = emit

    def check(self):
        if self.cancelled.is_set():
            raise WorkCancelled("Work was cancelled")

    def cancel(self):
        with self.lock:
            if self.committed:
                return False
            self.cancelled.set()
            if self.response is not None:
                try:
                    self.response.close()
                except Exception:
                    logging.getLogger(__name__).debug(
                        "Cancelled response could not close", exc_info=True
                    )
            return True

    def commit(self, action):
        with self.lock:
            self.check()
            result = action()
            self.committed = True
            return result


def current_control():
    return _context.get()


def checkpoint(stage=None):
    control = current_control()
    if control:
        control.check()
        if stage:
            control.progress(stage)


def publish(action):
    control = current_control()
    return control.commit(action) if control else action()


@contextmanager
def execution(control):
    token = _context.set(control)
    try:
        yield
    finally:
        _context.reset(token)
