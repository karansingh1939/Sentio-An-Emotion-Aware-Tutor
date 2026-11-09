"""Invalid generated practice is repaired or regenerated before falling back to source recall."""

import json
import time

from fastapi.testclient import TestClient

from sentio.ai.providers import OllamaBackend
from sentio.api.app import app
from sentio.shared.exceptions import InvalidModelOutput
from tests.helpers import complete, login_student

NOTES = b"Inertia resists changes in velocity. A net force changes velocity. Mass measures inertia."


def _session(client):
    owner = login_student(client)
    doc = client.post(
        "/api/v1/documents/upload", files={"file": ("notes.txt", NOTES, "text/plain")}
    ).json()["document_id"]
    session_id = client.post(
        "/api/v1/sessions",
        json={
            "student_id": owner,
            "subject": "physics",
            "topic": "Inertia",
            "metadata": {"document_id": doc},
        },
    ).json()["session_id"]
    return owner, session_id


def _finish(client, job):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = client.get("/api/v1/jobs/" + job["job_id"]).json()
        if result["status"] in {"succeeded", "failed", "cancelled"}:
            return result
        time.sleep(0.03)
    raise AssertionError(f"Job did not finish: {result}")


def _invalid_first(monkeypatch, invalid):
    calls = []

    def provider(self, system_prompt, history, user_message, **kwargs):
        calls.append(user_message)
        if len(calls) == 1:
            raise InvalidModelOutput(invalid, "schema mismatch")
        return complete(system_prompt, history, user_message, **kwargs)

    monkeypatch.setattr(OllamaBackend, "complete", provider)
    return calls


def test_invalid_quiz_is_regenerated_instead_of_falling_back(monkeypatch):
    duplicate_options = {
        "question_text": "Which quantity measures inertia?",
        "question_type": "multiple_choice",
        "options": ["Mass", "Mass", "Force", "Speed"],
        "correct_answer": "Mass",
        "explanation": "Mass measures inertia.",
    }
    calls = _invalid_first(
        monkeypatch, json.dumps({"title": "Inertia", "questions": [duplicate_options] * 3})
    )
    with TestClient(app) as client:
        owner, session_id = _session(client)
        job = client.post(
            "/api/v1/quizzes/jobs",
            json={
                "student_id": owner,
                "session_id": session_id,
                "subject": "physics",
                "topic": "Inertia",
                "num_questions": 3,
            },
        ).json()
        result = _finish(client, job)
        assert result["status"] == "succeeded", result
        quiz = client.get("/api/v1/quizzes/" + result["result"]["quiz_id"]).json()
    assert quiz["provenance"]["mode"] == "generated"
    assert len(calls) == 2 and "Return exactly 3 questions" in calls[1]


def test_valid_quiz_questions_are_kept_and_only_missing_ones_regenerated(monkeypatch):
    """A slow local model should not rewrite a whole batch to replace one bad item."""
    good = {
        "question_text": "Which quantity measures inertia?",
        "question_type": "multiple_choice",
        "options": ["Mass", "Force", "Speed", "Time"],
        "correct_answer": "Mass",
        "explanation": "Mass measures inertia.",
    }
    also_good = {**good, "question_text": "What changes velocity?", "correct_answer": "Force"}
    broken = {**good, "question_text": "Pick one", "correct_answer": "Weight"}  # not an option
    calls = _invalid_first(
        monkeypatch, json.dumps({"title": "Inertia", "questions": [good, also_good, broken]})
    )
    with TestClient(app) as client:
        owner, session_id = _session(client)
        job = client.post(
            "/api/v1/quizzes/jobs",
            json={
                "student_id": owner,
                "session_id": session_id,
                "subject": "physics",
                "topic": "Inertia",
                "num_questions": 3,
            },
        ).json()
        result = _finish(client, job)
        assert result["status"] == "succeeded", result
        quiz = client.get("/api/v1/quizzes/" + result["result"]["quiz_id"]).json()
    texts = [q["question_text"] for q in quiz["questions"]]
    assert quiz["provenance"]["mode"] == "generated"
    assert texts[:2] == [good["question_text"], also_good["question_text"]]
    assert len(texts) == 3 and "Pick one" not in texts
    assert len(calls) == 2 and "Return exactly 1 questions" in calls[1]


def test_invalid_flashcards_are_regenerated_instead_of_falling_back(monkeypatch):
    calls = _invalid_first(monkeypatch, '{"deck_name": "Inertia", "cards": []}')
    with TestClient(app) as client:
        owner, session_id = _session(client)
        deck = client.post(
            "/api/v1/flashcards/decks", json={"student_id": owner, "deck_name": "Inertia"}
        ).json()["deck_id"]
        job = client.post(
            "/api/v1/flashcards/jobs",
            json={
                "deck_id": deck,
                "student_id": owner,
                "session_id": session_id,
                "topic_id": "Inertia",
                "num_cards": 3,
            },
        ).json()
        assert _finish(client, job)["status"] == "succeeded"
        cards = client.get(f"/api/v1/flashcards/reviews/due?student_id={owner}").json()["cards"]
    assert cards and {card["provenance"]["mode"] for card in cards} == {"generated"}
    assert len(calls) == 2
