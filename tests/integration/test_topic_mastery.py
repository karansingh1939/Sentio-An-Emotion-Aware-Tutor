"""Lecture topics come from slides, and quiz answers move each topic towards Ready."""

import json
from io import BytesIO

from fastapi.testclient import TestClient
from pptx import Presentation

from sentio.ai.providers import OllamaBackend
from sentio.api.app import app
from tests.helpers import complete, login_student

SLIDES = [
    ("Paging", "Paging splits memory into fixed size frames."),
    ("Paging (cont.)", "A page table maps each page to a frame."),
    ("Deadlock", "Deadlock needs circular wait and hold and wait."),
]
QUESTIONS = {
    "paging": {
        "question_text": "What does paging split memory into?",
        "question_type": "multiple_choice",
        "options": ["Frames", "Threads", "Files", "Sockets"],
        "correct_answer": "Frames",
        "explanation": "Paging splits memory into fixed size frames.",
        "difficulty": "beginner",
        "topic": "x",
    },
    "deadlock": {
        "question_text": "Which condition does deadlock need?",
        "question_type": "multiple_choice",
        "options": ["Circular wait", "Paging", "Caching", "Hashing"],
        "correct_answer": "Circular wait",
        "explanation": "Deadlock needs circular wait.",
        "difficulty": "beginner",
        "topic": "x",
    },
}


def _deck():
    deck = Presentation()
    for title, body in SLIDES:
        slide = deck.slides.add_slide(deck.slide_layouts[1])
        slide.shapes.title.text = title
        slide.placeholders[1].text_frame.text = body
    buffer = BytesIO()
    deck.save(buffer)
    return buffer.getvalue()


def _provider(kind):
    def provider(self, system_prompt, history, user_message, **kwargs):
        if "generate a quiz" in system_prompt.lower():
            return json.dumps({"title": "Practice", "questions": [QUESTIONS[kind]] * 3}), 30
        return complete(system_prompt, history, user_message, **kwargs)

    return provider


def _study(client):
    owner = login_student(client)
    course = client.post("/api/v1/courses", json={"name": "Operating Systems"}).json()
    mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    document = client.post(
        "/api/v1/documents/upload",
        files={"file": ("memory.pptx", _deck(), mime)},
        data={"category": "notes", "course_id": course["id"]},
    ).json()["document_id"]
    session = client.post(
        "/api/v1/sessions",
        json={"student_id": owner, "topic": "Review", "metadata": {"document_id": document}},
    ).json()["session_id"]
    return owner, course["id"], document, session


def _quiz(client, monkeypatch, owner, session, kind, answer):
    monkeypatch.setattr(OllamaBackend, "complete", _provider(kind))
    quiz = client.post(
        "/api/v1/quizzes/generate",
        json={"student_id": owner, "session_id": session, "topic": kind, "num_questions": 3},
    )
    assert quiz.status_code == 200, quiz.text
    submitted = client.post(
        f"/api/v1/quizzes/{quiz.json()['quiz_id']}/submit",
        json={"session_id": session, "answers": {i: answer for i in range(3)}},
    )
    assert submitted.status_code == 200, submitted.text


def _states(lecture):
    return {t["title"]: (t["state"], t["answers"], t["recent_correct"]) for t in lecture["topics"]}


def test_topics_follow_slides_and_quiz_answers_set_their_state(monkeypatch):
    with TestClient(app) as client:
        owner, course, document, session = _study(client)
        lecture = client.get(f"/api/v1/documents/{document}/topics").json()
        assert [(t["title"], t["first_page"], t["last_page"]) for t in lecture["topics"]] == [
            ("Paging", 1, 2),
            ("Deadlock", 3, 3),
        ]
        assert _states(lecture) == {
            "Paging": ("not_started", 0, 0),
            "Deadlock": ("not_started", 0, 0),
        }

        _quiz(client, monkeypatch, owner, session, "paging", "Frames")
        _quiz(client, monkeypatch, owner, session, "paging", "Frames")
        _quiz(client, monkeypatch, owner, session, "deadlock", "Paging")
        lecture = client.get(f"/api/v1/documents/{document}/topics").json()
        assert _states(lecture) == {
            "Paging": ("ready", 6, 5),
            "Deadlock": ("practising", 3, 0),
        }

        progress = client.get(f"/api/v1/courses/{course}/progress").json()
        assert progress["summary"] == {"ready": 1, "practising": 1, "not_started": 0, "total": 2}
        assert [t["title"] for t in progress["weak"]] == ["Deadlock"]
        assert progress["weak"][0]["filename"] == "memory.pptx"

        login_student(client)
        assert client.get(f"/api/v1/documents/{document}/topics").status_code == 404
        assert client.get(f"/api/v1/courses/{course}/progress").status_code == 404


def test_topics_can_be_renamed_and_merged_by_their_owner_only():
    with TestClient(app) as client:
        _, _, document, _ = _study(client)
        paging, deadlock = client.get(f"/api/v1/documents/{document}/topics").json()["topics"]
        assert client.post(f"/api/v1/topics/{paging['id']}/merge").status_code == 404  # first
        renamed = client.patch(f"/api/v1/topics/{deadlock['id']}", json={"name": "Deadlocks"})
        assert renamed.status_code == 200
        assert client.post(f"/api/v1/topics/{deadlock['id']}/merge").json() == {"merged": True}
        topics = client.get(f"/api/v1/documents/{document}/topics").json()["topics"]
        assert [(t["title"], t["first_page"], t["last_page"]) for t in topics] == [("Paging", 1, 3)]

        login_student(client)
        assert (
            client.patch(f"/api/v1/topics/{paging['id']}", json={"name": "Mine"}).status_code == 404
        )


def test_topics_are_rebuilt_when_the_lecture_changes_and_removed_with_it():
    with TestClient(app) as client:
        _, _, document, _ = _study(client)
        first = client.get(f"/api/v1/documents/{document}/topics").json()["topics"]
        client.patch(f"/api/v1/topics/{first[0]['id']}", json={"name": "Renamed"})
        changed = Presentation(BytesIO(_deck()))
        changed.slides[2].shapes.title.text = "Scheduling"
        buffer = BytesIO()
        changed.save(buffer)
        mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        client.post(
            "/api/v1/documents/upload",
            files={"file": ("memory.pptx", buffer.getvalue(), mime)},
            data={"category": "notes"},
        )
        titles = [
            t["title"] for t in client.get(f"/api/v1/documents/{document}/topics").json()["topics"]
        ]
        assert titles == ["Paging", "Scheduling"]

        assert client.delete(f"/api/v1/documents/{document}").status_code == 200
        assert client.get(f"/api/v1/documents/{document}/topics").status_code == 404
