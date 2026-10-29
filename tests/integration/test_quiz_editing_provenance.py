"""Saved practice records where it came from, and owners can correct generated quizzes."""

import time

from fastapi.testclient import TestClient

from sentio.api.app import agent, app
from sentio.shared.exceptions import LLMServiceUnavailableError
from tests.helpers import login_student

NOTES = b"Inertia resists changes in velocity. A net force changes velocity. Mass measures inertia."


def _study(client):
    owner = login_student(client)
    upload = client.post(
        "/api/v1/documents/upload", files={"file": ("notes.txt", NOTES, "text/plain")}
    )
    assert upload.status_code == 201, upload.text
    doc = upload.json()["document_id"]
    session = client.post(
        "/api/v1/sessions",
        json={
            "student_id": owner,
            "subject": "physics",
            "topic": "Inertia",
            "metadata": {"document_id": doc},
        },
    )
    assert session.status_code == 201, session.text
    return owner, doc, session.json()["session_id"]


def _finish(client, job):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = client.get("/api/v1/jobs/" + job["job_id"]).json()
        if result["status"] in {"succeeded", "failed", "cancelled"}:
            return result
        time.sleep(0.03)
    raise AssertionError(f"Job did not finish: {result}")


def _quiz(client, owner, session_id):
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
    return client.get("/api/v1/quizzes/" + result["result"]["quiz_id"]).json()


def test_generated_quiz_records_model_sources_and_document_versions():
    with TestClient(app) as client:
        owner, doc, session_id = _study(client)
        quiz = _quiz(client, owner, session_id)
        provenance = quiz["provenance"]
        assert provenance["mode"] == "generated"
        assert provenance["model"]
        assert {source["filename"] for source in provenance["sources"]} == {"notes.txt"}
        checksum = next(d["checksum"] for d in agent.sm.list_documents(student_id=owner))
        assert provenance["documents"] == [[doc, checksum]]
        assert quiz["revision"] == 0 and all(q["question_id"] for q in quiz["questions"])
        listed = client.get("/api/v1/quizzes").json()
        entry = next(item for item in listed["quizzes"] if item["quiz_id"] == quiz["quiz_id"])
        assert entry["provenance"]["mode"] == "generated"


def test_fallback_practice_is_labelled_source_recall(monkeypatch):
    def unavailable(**kwargs):
        raise LLMServiceUnavailableError("ollama", "Unavailable test provider")

    with TestClient(app) as client:
        owner, _, session_id = _study(client)
        monkeypatch.setattr(agent.nlp._backend, "complete", unavailable)
        quiz = _quiz(client, owner, session_id)
        assert quiz["provenance"]["mode"] == "source_recall"
        assert quiz["provenance"]["sources"][0]["filename"] == "notes.txt"

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
        assert cards and {card["provenance"]["mode"] for card in cards} == {"source_recall"}


def test_owner_edits_a_question_and_new_answers_use_the_correction():
    with TestClient(app) as client:
        owner, _, session_id = _study(client)
        quiz = _quiz(client, owner, session_id)
        question = quiz["questions"][0]
        path = f"/api/v1/quizzes/{quiz['quiz_id']}/questions/{question['question_id']}"
        options = question["options"] or ["Entropy", "Energy"]
        wrong = next(option for option in options if option != question["correct_answer"])

        answers = {"session_id": session_id, "answers": {"0": wrong}}
        before = client.post(f"/api/v1/quizzes/{quiz['quiz_id']}/submit", json=answers).json()
        assert before["feedback"][0]["is_correct"] is False

        edit = {
            "question_text": "Corrected question?",
            "options": question["options"],
            "correct_answer": wrong,
            "explanation": "Corrected by the learner.",
            "expected_revision": 0,
        }
        saved = client.put(path, json=edit)
        assert saved.status_code == 200, saved.text
        assert saved.json()["revision"] == 1
        stored = client.get("/api/v1/quizzes/" + quiz["quiz_id"]).json()
        assert stored["questions"][0]["question_text"] == "Corrected question?"
        assert stored["provenance"]["edited"] is True

        after = client.post(f"/api/v1/quizzes/{quiz['quiz_id']}/submit", json=answers).json()
        assert after["feedback"][0]["is_correct"] is True

        stale = client.put(path, json=edit)
        assert stale.status_code == 409


def test_question_edits_are_validated_and_owner_scoped():
    with TestClient(app) as client:
        owner, _, session_id = _study(client)
        quiz = _quiz(client, owner, session_id)
        question = next(q for q in quiz["questions"] if q["question_type"] == "multiple_choice")
        path = f"/api/v1/quizzes/{quiz['quiz_id']}/questions/{question['question_id']}"
        base = {
            "question_text": "Which quantity measures disorder?",
            "options": question["options"],
            "correct_answer": question["correct_answer"],
            "explanation": "Explanation",
        }
        not_an_option = {**base, "correct_answer": "Not listed"}
        assert client.put(path, json=not_an_option).status_code == 422
        assert client.put(path, json={**base, "question_text": "   "}).status_code == 422

        login_student(client)
        assert client.put(path, json=base).status_code == 404
