import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from sentio.ai.source_practice import source_excerpt, source_recall
from sentio.api.app import agent, app
from sentio.shared.exceptions import LLMServiceUnavailableError
from tests.helpers import login_student


def test_source_recall_uses_only_exact_passage_words_and_citations():
    source = SimpleNamespace(
        source_citations=[
            {
                "filename": "notes.txt",
                "page": 1,
                "text": "Inertia resists changes in velocity. A net force changes velocity. Mass measures inertia.",
            }
        ]
    )
    questions = source_recall(source, 3)
    assert len(questions) == 3
    for question in questions:
        assert question["question_type"] == "fill_in_the_blank"
        assert "[notes.txt Page 1]" in question["explanation"]
        restored = (
            question["question_text"].split("\n", 1)[1].replace("_____", question["correct_answer"])
        )
        assert restored in source.source_citations[0]["text"]
    assert "could not verify" in source_excerpt(source)
    with pytest.raises(ValueError, match="Not enough"):
        source_recall(source, 4)


def test_provider_failure_keeps_selected_notes_usable_and_resumed_practice_persistent(monkeypatch):
    with TestClient(app) as client:
        owner = login_student(client)
        doc = client.post(
            "/api/v1/documents/upload",
            files={
                "file": (
                    "notes.txt",
                    b"Inertia resists changes in velocity. A net force changes velocity. Mass measures inertia.",
                    "text/plain",
                )
            },
        ).json()["document_id"]
        sid = client.post(
            "/api/v1/sessions",
            json={
                "student_id": owner,
                "subject": "physics",
                "topic": "Inertia",
                "metadata": {"document_id": doc},
            },
        ).json()["session_id"]

        def unavailable(**kwargs):
            raise LLMServiceUnavailableError("ollama", "Unavailable test provider")

        monkeypatch.setattr(agent.nlp._backend, "complete", unavailable)
        stream = client.post(
            f"/api/v1/sessions/{sid}/chat/stream",
            json={"message": "What is inertia?", "request_id": "source-fallback-test"},
        )
        assert "event: complete" in stream.text
        assert "source_excerpt" in stream.text and "could not verify" in stream.text
        assert client.delete("/api/v1/sessions/" + sid).status_code == 200
        assert client.post(f"/api/v1/sessions/{sid}/resume").status_code == 200
        stored = agent.sm.persister.load_session_data(sid)
        assert stored["status"] == "active" and stored["closed_at"] is None
        job = client.post(
            "/api/v1/quizzes/jobs",
            json={
                "student_id": owner,
                "session_id": sid,
                "subject": "physics",
                "topic": "Inertia",
                "num_questions": 3,
            },
        ).json()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = client.get("/api/v1/jobs/" + job["job_id"]).json()
            if result["status"] in {"succeeded", "failed", "cancelled"}:
                break
            time.sleep(0.03)
        assert result["status"] == "succeeded", result
        quiz = client.get("/api/v1/quizzes/" + result["result"]["quiz_id"]).json()
        assert quiz["title"].startswith("Source recall:") and len(quiz["questions"]) == 3
        for question in quiz["questions"]:
            assert "[notes.txt Page 1]" in question["explanation"]
        agent.sm._sessions.pop(sid)
        assert agent.sm.get_session(sid).status.value == "active"
