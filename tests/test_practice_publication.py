import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from sentio.api.app import agent, app
from sentio.jobs.control import WorkCancelled
from sentio.repositories.practice_repository import PracticeRepository
from tests.test_study_planning import account


@pytest.mark.parametrize("kind", ["quizzes", "flashcards"])
def test_context_change_during_generation_does_not_save_practice(monkeypatch, kind):
    with TestClient(app) as client:
        headers, owner = account(client, f"stale-{kind}@example.com")
        session_id = client.post(
            "/api/v1/sessions",
            headers=headers,
            json={
                "student_id": owner,
                "subject": "physics",
                "topic": "Inertia",
                "difficulty": "beginner",
            },
        ).json()["session_id"]
        payload = {
            "session_id": session_id,
            "student_id": owner,
            "subject": "physics",
            "topic": "Inertia",
            "difficulty": "beginner",
        }
        if kind == "flashcards":
            payload["topic_id"] = "Inertia"
            payload["deck_id"] = client.post(
                "/api/v1/flashcards/decks",
                headers=headers,
                json={"student_id": owner, "deck_name": "Notes"},
            ).json()["deck_id"]
        original = agent.nlp._backend.complete

        def switch_context(*args, **kwargs):
            result = original(*args, **kwargs)
            current = agent.sm.get_or_raise(session_id)
            current.topic = "Thermodynamics"
            agent.sm.persister.save_session(current)
            return result

        monkeypatch.setattr(agent.nlp._backend, "complete", switch_context)
        response = client.post(f"/api/v1/{kind}/jobs", headers=headers, json=payload)
        assert response.status_code == 202, response.text
        path = "/api/v1/jobs/" + response.json()["job_id"]
        for _ in range(100):
            state = client.get(path, headers=headers).json()
            if state["status"] in ("succeeded", "failed", "cancelled"):
                break
            time.sleep(0.02)
        assert state["status"] == "cancelled", state
        table = "quizzes" if kind == "quizzes" else "flashcards"
        with agent.sm.persister._engine.connect() as connection:
            assert (
                connection.execute(
                    text(f"SELECT COUNT(*) FROM {table} WHERE student_id=:owner"), {"owner": owner}
                ).scalar()
                == 0
            )


def test_document_revision_is_part_of_practice_publication_contract():
    with TestClient(app) as client:
        headers, owner = account(client, "revision-practice@example.com")
        uploaded = client.post(
            "/api/v1/documents/upload",
            headers=headers,
            files={
                "file": ("inertia.txt", b"Inertia is resistance to change in motion.", "text/plain")
            },
            data={"category": "notes", "subject": "physics"},
        )
        assert uploaded.status_code == 201, uploaded.text
        documents = agent.sm.list_documents(student_id=owner)
        source = documents[0]["id"]
        session_id = client.post(
            "/api/v1/sessions",
            headers=headers,
            json={
                "student_id": owner,
                "subject": "physics",
                "topic": "Inertia",
                "difficulty": "beginner",
                "metadata": {"document_id": source},
            },
        ).json()["session_id"]
        session = agent.sm.get_or_raise(session_id)
        repository = PracticeRepository(agent.sm.persister._engine)
        before = repository.snapshot(session)
        with agent.sm.persister._engine.begin() as connection:
            connection.execute(
                text("UPDATE documents SET checksum='replaced' WHERE id=:id"), {"id": source}
            )
        assert repository.snapshot(session) != before
        with pytest.raises(WorkCancelled, match="context changed"):
            with repository.publication(session, before):
                pytest.fail("A replaced source must not publish an earlier result")
