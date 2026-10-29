import json
import time

from fastapi.testclient import TestClient

from sentio.api.app import agent, app
from tests.helpers import login_student


def test_wrong_question_count_is_not_published(monkeypatch):
    question = {
        "question_text": "What changes velocity?",
        "question_type": "short_answer",
        "correct_answer": "Net force",
        "explanation": "A net force causes acceleration.",
    }
    with TestClient(app) as client:
        owner = login_student(client)
        sid = client.post(
            "/api/v1/sessions",
            json={
                "student_id": owner,
                "subject": "physics",
                "topic": "motion",
                "difficulty": "beginner",
            },
        ).json()["session_id"]
        monkeypatch.setattr(
            agent.nlp._backend,
            "complete",
            lambda **kwargs: (
                json.dumps({"title": "Wrong count", "questions": [question, question]}),
                30,
            ),
        )
        job = client.post(
            "/api/v1/quizzes/jobs",
            json={
                "student_id": owner,
                "session_id": sid,
                "subject": "physics",
                "topic": "motion",
                "num_questions": 1,
            },
        ).json()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = client.get("/api/v1/jobs/" + job["job_id"]).json()
            if status["status"] in {"succeeded", "failed"}:
                break
            time.sleep(0.03)
        assert status["status"] == "failed"
        assert client.get("/api/v1/quizzes").json()["quizzes"] == []
