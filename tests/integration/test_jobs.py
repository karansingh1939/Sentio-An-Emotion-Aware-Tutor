import threading

import pytest
from sqlalchemy import create_engine, text

from sentio.jobs.service import JobManager
from sentio.repositories.migrations import apply_migrations


def test_failed_migration_rolls_back_ddl_and_version(tmp_path, monkeypatch):
    from sentio.repositories import migrations

    engine = create_engine(f"sqlite:///{tmp_path / 'schema.db'}")
    apply_migrations(engine)
    original_versions = len(migrations.MIGRATIONS)
    monkeypatch.setitem(
        migrations.MIGRATIONS,
        max(migrations.MIGRATIONS) + 1,
        ["CREATE TABLE transient (id TEXT)", "INVALID SQL"],
    )
    with pytest.raises(Exception):
        apply_migrations(engine)
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT COUNT(*) FROM schema_migrations")).scalar()
            == original_versions
        )
        assert not connection.execute(
            text("SELECT name FROM sqlite_master WHERE name='transient'")
        ).first()
    engine.dispose()


def test_cancel_cannot_undo_published_artifact(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    apply_migrations(engine)
    manager = JobManager(engine)
    published = threading.Event()
    release = threading.Event()

    def work(control):
        control.commit(lambda: published.set())
        release.wait(3)
        return {"saved": True}

    job = manager.submit("owner", "test", work)
    assert published.wait(3)
    assert not manager.cancel(job["job_id"], "owner")
    release.set()
    manager.close()
    assert manager.get(job["job_id"], "owner")["status"] == "succeeded"
    engine.dispose()


def test_practice_jobs_api_persists_results_and_hides_other_owners():
    import time

    from fastapi.testclient import TestClient

    from sentio.api.app import app

    with TestClient(app) as client:

        def account(email):
            response = client.post(
                "/api/v1/auth/register", json={"email": email, "password": "StrongPassword123!"}
            )
            assert response.status_code == 201, response.text
            login = client.post(
                "/api/v1/auth/login", json={"email": email, "password": "StrongPassword123!"}
            )
            return {"Authorization": "Bearer " + login.json()["access_token"]}

        owner = account("job-owner@example.com")
        other = account("job-other@example.com")
        response = client.post(
            "/api/v1/sessions",
            headers=owner,
            json={
                "student_id": "ignored",
                "subject": "physics",
                "topic": "Newton's First Law",
                "difficulty": "beginner",
            },
        )
        assert response.status_code in (200, 201), response.text
        session = response.json()["session_id"]
        job = client.post(
            "/api/v1/quizzes/jobs",
            headers=owner,
            json={
                "student_id": "ignored",
                "session_id": session,
                "subject": "physics",
                "topic": "ignored",
                "difficulty": "beginner",
                "num_questions": 3,
            },
        )
        assert job.status_code == 202, job.text
        path = "/api/v1/jobs/" + job.json()["job_id"]
        assert client.get(path, headers=other).status_code == 404
        assert client.post(path + "/cancel", headers=other).status_code == 404
        for _ in range(50):
            state = client.get(path, headers=owner).json()
            if state["status"] in ("succeeded", "failed", "cancelled"):
                break
            time.sleep(0.05)
        assert state["status"] == "succeeded", state
        assert state["result"]["questions"][0]["topic"] == "Newton's First Law"


def test_jobs_are_owned_bounded_cancellable_and_persisted(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'jobs.db'}", connect_args={"check_same_thread": False}
    )
    apply_migrations(engine)
    manager = JobManager(engine, queue_limit=2)
    started = threading.Event()
    release = threading.Event()

    def slow(control):
        started.set()
        release.wait(5)
        control.check()
        return {"saved": True}

    first = manager.submit("owner", "test", slow)
    assert started.wait(3)
    second = manager.submit("owner", "test", slow)
    assert manager.get(first["job_id"], "other") is None
    with pytest.raises(ValueError, match="queue"):
        manager.submit("owner", "test", slow)
    assert manager.cancel(first["job_id"], "owner")
    assert manager.cancel(second["job_id"], "owner")
    release.set()
    manager.close()
    assert manager.get(first["job_id"], "owner")["status"] == "cancelled"
    assert manager.get(second["job_id"], "owner")["status"] == "cancelled"
    assert manager.get(first["job_id"], "owner")["result"] is None
    engine.dispose()


def test_restart_marks_interrupted_jobs_failed_without_replaying_side_effects(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    apply_migrations(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO jobs (job_id, student_id, kind, lane, status, stage, created_at, updated_at) VALUES ('old', 'owner', 'test', 'ai', 'running', 'generating', 1, 1)"
            )
        )
    manager = JobManager(engine)
    assert manager.get("old", "owner")["status"] == "failed"
    assert "interrupted" in manager.get("old", "owner")["error"].lower()
    manager.close()
    engine.dispose()


def test_migrations_are_repeatable_and_versions_are_recorded(tmp_path):
    from sentio.repositories.migrations import MIGRATIONS

    engine = create_engine(f"sqlite:///{tmp_path / 'schema.db'}")
    apply_migrations(engine)
    apply_migrations(engine)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM schema_migrations")).scalar() == len(
            MIGRATIONS
        )
        assert connection.execute(text("SELECT COUNT(*) FROM jobs")).scalar() == 0
    engine.dispose()


def test_terminal_job_state_cannot_be_overwritten_by_late_cancellation(tmp_path):
    from sentio.repositories.jobs import JobRepository

    engine = create_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    apply_migrations(engine)
    repository = JobRepository(engine)
    job = repository.create("owner", "test", "ai")
    repository.update(job["job_id"], "cancelled", "cancelled")
    repository.update(job["job_id"], "cancelling", "cancelling")
    repository.update(job["job_id"], "running", "late progress")
    assert repository.get(job["job_id"], "owner")["status"] == "cancelled"
    engine.dispose()
