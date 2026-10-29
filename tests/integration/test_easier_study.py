"""One-click study, sources before answers, instant answer checks and note overviews."""

import json
import time

from fastapi.testclient import TestClient
from sqlalchemy import text

from sentio.ai.providers import OllamaBackend
from sentio.api.app import agent, app
from tests.helpers import complete, login_student

NOTES = b"Inertia resists changes in velocity. A net force changes velocity. Mass measures inertia."
OVERVIEW = {
    "summary": "The notes define inertia and relate force, velocity and mass.",
    "key_concepts": ["Inertia", "Net force", "Mass"],
    "suggested_questions": ["What is inertia?", "What changes velocity?"],
}


def _study(client, subject="general"):
    owner = login_student(client)
    doc = client.post(
        "/api/v1/documents/upload", files={"file": ("notes.txt", NOTES, "text/plain")}
    ).json()["document_id"]
    response = client.post(
        "/api/v1/sessions",
        json={
            "student_id": owner,
            "subject": subject,
            "topic": "Inertia resists changes in velocity",
            "metadata": {"document_id": doc},
        },
    )
    assert response.status_code == 201, response.text
    return owner, doc, response.json()["session_id"]


def _finish(client, job):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = client.get("/api/v1/jobs/" + job["job_id"]).json()
        if result["status"] in {"succeeded", "failed", "cancelled"}:
            return result
        time.sleep(0.03)
    raise AssertionError(result)


def test_notes_can_be_studied_with_the_general_subject_of_uploads():
    with TestClient(app) as client:
        _, doc, session_id = _study(client)
        assert agent.sm.get_session(session_id).metadata["document_id"] == doc


def test_stream_shares_retrieved_sources_before_the_answer():
    with TestClient(app) as client:
        _, _, session_id = _study(client)
        stream = client.post(
            f"/api/v1/sessions/{session_id}/chat/stream",
            json={"message": "What is inertia?", "request_id": "sources-first-1"},
        ).text
    assert "event: sources" in stream
    assert stream.index("event: sources") < stream.index("event: complete")
    sources = json.loads(stream.split("event: sources\ndata: ")[1].split("\n")[0])["sources"]
    assert sources[0]["filename"] == "notes.txt" and "Inertia" in sources[0]["text"]


def test_answer_check_gives_feedback_without_recording_an_attempt():
    with TestClient(app) as client:
        owner, _, session_id = _study(client)
        job = client.post(
            "/api/v1/quizzes/jobs",
            json={
                "student_id": owner,
                "session_id": session_id,
                "subject": "general",
                "topic": "Inertia resists changes in velocity",
                "num_questions": 3,
            },
        ).json()
        quiz_id = _finish(client, job)["result"]["quiz_id"]
        quiz = client.get(f"/api/v1/quizzes/{quiz_id}").json()
        question = next(q for q in quiz["questions"] if q["question_type"] == "multiple_choice")
        path = f"/api/v1/quizzes/{quiz_id}/questions/{question['question_id']}/check"
        wrong = next(o for o in question["options"] if o != question["correct_answer"])

        right = client.post(path, json={"answer": question["correct_answer"]}).json()
        assert right["is_correct"] is True and right["explanation"]
        miss = client.post(path, json={"answer": wrong}).json()
        assert miss["is_correct"] is False
        assert miss["correct_answer"] == question["correct_answer"]
        with agent.sm.persister._engine.connect() as connection:
            attempts = connection.execute(
                text("SELECT COUNT(*) FROM quiz_attempts WHERE student_id=:owner"),
                {"owner": owner},
            ).scalar()
        assert attempts == 0

        login_student(client)
        assert client.post(path, json={"answer": wrong}).status_code == 404


def test_overview_is_generated_once_cached_and_owner_scoped(monkeypatch):
    calls = []

    def provider(self, system_prompt, history, user_message, **kwargs):
        if system_prompt.startswith("You summarize a learner's own notes."):
            calls.append(system_prompt)
            return json.dumps(OVERVIEW), 30
        return complete(system_prompt, history, user_message, **kwargs)

    monkeypatch.setattr(OllamaBackend, "complete", provider)
    with TestClient(app) as client:
        _, doc, _ = _study(client)
        path = f"/api/v1/documents/{doc}/overview"
        assert client.get(path).json() == {"overview": None}

        job = client.post(path + "/jobs").json()
        result = _finish(client, job)
        assert result["status"] == "succeeded", result
        assert result["result"]["suggested_questions"] == OVERVIEW["suggested_questions"]
        assert "Inertia resists changes in velocity" in calls[0]
        assert client.get(path).json()["overview"]["summary"] == OVERVIEW["summary"]

        again = _finish(client, client.post(path + "/jobs").json())
        assert again["result"]["summary"] == OVERVIEW["summary"] and len(calls) == 1

        login_student(client)
        assert client.get(path).status_code == 404
        assert client.post(path + "/jobs").status_code == 404
