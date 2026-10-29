import threading

import pytest
from sqlalchemy import create_engine

from sentio.jobs.service import JobManager
from sentio.repositories.migrations import apply_migrations


def test_unknown_submission_retry_reuses_running_job_and_checks_payload(tmp_path):
    from sentio.repositories.jobs import JobConflict, JobExpired

    engine = create_engine(f"sqlite:///{tmp_path / 'submissions.db'}")
    apply_migrations(engine)
    manager = JobManager(engine, queue_limit=1)
    release = threading.Event()
    calls = []

    def work(control):
        calls.append(1)
        release.wait(2)
        return {"saved": True}

    try:
        first = manager.submit(
            "owner", "quiz", work, request_id="same-intent", fingerprint="body-a"
        )
        assert (
            manager.submit("owner", "quiz", work, request_id="same-intent", fingerprint="body-a")[
                "job_id"
            ]
            == first["job_id"]
        )
        with pytest.raises(JobConflict):
            manager.submit("owner", "quiz", work, request_id="same-intent", fingerprint="body-b")
        release.set()
        manager.close()
        restored = JobManager(engine)
        assert (
            restored.submit("owner", "quiz", work, request_id="same-intent", fingerprint="body-a")[
                "job_id"
            ]
            == first["job_id"]
        )
        from sqlalchemy import text

        with engine.begin() as connection:
            connection.execute(text("DELETE FROM jobs WHERE job_id=:id"), {"id": first["job_id"]})
        with pytest.raises(JobExpired):
            restored.submit("owner", "quiz", work, request_id="same-intent", fingerprint="body-a")
        restored.close()
        assert calls == [1]
    finally:
        release.set()
        manager.close()
        engine.dispose()
