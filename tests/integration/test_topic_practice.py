"""Practising a topic quizzes on exactly its slides, and every answer counts for it."""

import json

from fastapi.testclient import TestClient

from sentio.ai.providers import OllamaBackend
from sentio.api.app import app
from sentio.shared.exceptions import LLMServiceUnavailableError
from tests.helpers import complete, login_student
from tests.integration.test_topic_mastery import QUESTIONS, _study

GENERIC = {
    **QUESTIONS["paging"],
    "question_text": "Which option is right?",
    "options": ["Xylophone", "Quartz", "Violet", "Zebra"],
    "correct_answer": "Xylophone",
    "explanation": "",
}


def _topics(client, document):
    topics = client.get(f"/api/v1/documents/{document}/topics").json()["topics"]
    return {topic["title"]: topic for topic in topics}


def _session(client, owner, source, topic_ids):
    return client.post(
        "/api/v1/sessions",
        json={
            "student_id": owner,
            "topic": "Practice",
            "metadata": {"document_id": source, "topic_ids": topic_ids},
        },
    )


def _quiz(client, owner, session, count=3):
    return client.post(
        "/api/v1/quizzes/generate",
        json={"student_id": owner, "session_id": session, "topic": "x", "num_questions": count},
    )


def _model(monkeypatch, questions, prompts=None):
    def provider(self, system_prompt, history, user_message, **kwargs):
        if "generate a quiz" in system_prompt.lower():
            if prompts is not None:
                prompts.append(system_prompt)
            return json.dumps({"title": "Practice", "questions": questions}), 30
        return complete(system_prompt, history, user_message, **kwargs)

    monkeypatch.setattr(OllamaBackend, "complete", provider)


def test_a_topic_quiz_uses_only_its_slides_and_answers_count_for_it(monkeypatch):
    with TestClient(app) as client:
        owner, _, document, _ = _study(client)
        paging = _topics(client, document)["Paging"]
        session = _session(client, owner, document, [paging["id"]]).json()["session_id"]

        prompts = []
        _model(monkeypatch, [GENERIC] * 3, prompts)  # No slide named, no words in common.
        quiz = _quiz(client, owner, session)
        assert quiz.status_code == 200, quiz.text
        assert "A page table maps each page to a frame." in prompts[0]
        assert "Citation Index: 2 | Topic: Paging" in prompts[0]
        assert "circular wait" not in prompts[0]

        quiz = quiz.json()
        assert {q["source_page"] for q in quiz["questions"]} == {1}
        assert {q["topic"] for q in quiz["questions"]} == {"Paging"}
        assert "source" not in quiz["questions"][0]
        assert quiz["provenance"]["located"] == {"topic": 3}
        assert quiz["provenance"]["topics"] == [
            {"title": "Paging", "filename": "memory.pptx", "first_page": 1, "last_page": 2}
        ]

        client.post(
            f"/api/v1/quizzes/{quiz['quiz_id']}/submit",
            json={"session_id": session, "answers": {i: "Xylophone" for i in range(3)}},
        )
        topics = _topics(client, document)
        assert (topics["Paging"]["state"], topics["Paging"]["answers"]) == ("ready", 3)
        assert topics["Deadlock"]["answers"] == 0


def test_the_slide_the_model_names_is_kept_only_when_it_checks_out(monkeypatch):
    with TestClient(app) as client:
        owner, _, document, _ = _study(client)
        paging = _topics(client, document)["Paging"]
        session = _session(client, owner, document, [paging["id"]]).json()["session_id"]
        table = {
            **QUESTIONS["paging"],
            "question_text": "What does a page table map?",
            "explanation": "It maps each page to a frame.",
        }
        _model(
            monkeypatch,
            [
                {**table, "source": 2},  # Correct.
                {**QUESTIONS["paging"], "source": 99},  # No such passage: word overlap decides.
                {**GENERIC, "source": "[2]"},  # Oddly written, and nothing in common with it.
            ],
        )
        quiz = _quiz(client, owner, session).json()
        assert [q["source_page"] for q in quiz["questions"]] == [2, 1, 1]
        assert quiz["provenance"]["located"] == {"model": 1, "overlap": 1, "topic": 1}


def test_several_topics_each_get_questions(monkeypatch):
    with TestClient(app) as client:
        owner, course, document, _ = _study(client)
        topics = _topics(client, document)
        session = _session(
            client,
            owner,
            f"course:{course}",
            [topics["Paging"]["id"], topics["Deadlock"]["id"]],
        ).json()["session_id"]
        prompts = []
        _model(monkeypatch, [GENERIC] * 3, prompts)
        quiz = _quiz(client, owner, session).json()
        assert "question 2 on 'Deadlock'" in prompts[0]
        assert [q["topic"] for q in quiz["questions"]] == ["Paging", "Deadlock", "Paging"]

        def unavailable(self, *args, **kwargs):
            raise LLMServiceUnavailableError("ollama", "Unavailable test provider")

        monkeypatch.setattr(OllamaBackend, "complete", unavailable)
        quiz = _quiz(client, owner, session).json()
        assert quiz["provenance"]["mode"] == "source_recall"
        assert {q["topic"] for q in quiz["questions"]} == {"Paging", "Deadlock"}


def test_only_the_students_own_topics_in_these_notes_can_be_chosen():
    with TestClient(app) as client:
        owner, _, document, _ = _study(client)
        topic = _topics(client, document)["Paging"]["id"]
        assert _session(client, owner, document, [topic, topic]).status_code == 422
        assert _session(client, owner, document, "paging").status_code == 422
        assert _session(client, owner, document, []).status_code == 422
        assert _session(client, owner, document, ["missing"]).status_code == 404
        assert _session(client, owner, "none", [topic]).status_code == 404
        assert _session(client, owner, "all", [topic]).status_code == 201

        stranger = login_student(client)
        assert _session(client, stranger, "all", [topic]).status_code == 404


def test_a_changed_topic_is_refused_and_changing_notes_clears_the_topics(monkeypatch):
    with TestClient(app) as client:
        owner, _, document, _ = _study(client)
        topics = _topics(client, document)
        deadlock, paging = topics["Deadlock"]["id"], topics["Paging"]["id"]
        session = _session(client, owner, document, [deadlock]).json()["session_id"]
        kept = _session(client, owner, document, [paging]).json()["session_id"]
        assert client.post(f"/api/v1/topics/{deadlock}/merge").status_code == 200

        _model(monkeypatch, [QUESTIONS["paging"]] * 3)
        refused = _quiz(client, owner, session)
        assert refused.status_code == 409
        assert "This topic changed" in refused.json()["detail"]
        job = client.post(
            "/api/v1/quizzes/jobs",
            json={"student_id": owner, "session_id": session, "topic": "x", "num_questions": 3},
        )
        assert job.status_code == 409

        assert client.get(f"/api/v1/sessions/{kept}/context").json()["topics"] == [paging]
        assert (
            client.post(
                f"/api/v1/sessions/{kept}/grounding", json={"document_id": document}
            ).status_code
            == 200
        )
        assert client.get(f"/api/v1/sessions/{kept}/context").json()["topics"] == []


def test_a_rebuilt_topic_map_keeps_its_ids():
    from sqlalchemy import text

    from sentio.api.app import agent

    with TestClient(app) as client:
        _, _, document, _ = _study(client)
        first = client.get(f"/api/v1/documents/{document}/topics").json()["topics"]
        with agent.sm.persister._engine.begin() as connection:
            connection.execute(
                text("DELETE FROM note_topics WHERE document_id=:id"), {"id": document}
            )
        again = client.get(f"/api/v1/documents/{document}/topics").json()["topics"]
        assert [topic["id"] for topic in again] == [topic["id"] for topic in first]
