"""The learning path comes from the learner's own lecture topics, not a fixed curriculum."""

from fastapi.testclient import TestClient

from sentio.api.app import app
from tests.helpers import login_student
from tests.integration.test_topic_mastery import _quiz, _study
from tests.integration.test_topic_memory import _age


def _path(client, owner, course=None):
    query = f"?course_id={course}" if course else ""
    response = client.get(f"/api/v1/student/{owner}/learning_path{query}")
    assert response.status_code == 200, response.text
    return response.json()


def test_path_starts_with_new_topics_in_lecture_order():
    with TestClient(app) as client:
        owner, course, document, _ = _study(client)
        path = _path(client, owner, course)
        assert (path["total"], path["ready"]) == (2, 0)
        assert [(s["title"], s["action"]) for s in path["steps"]] == [
            ("Paging", "learn"),
            ("Deadlock", "learn"),
        ]
        assert path["steps"][0]["document_id"] == document
        assert (path["steps"][0]["first_page"], path["steps"][0]["last_page"]) == (1, 2)
        assert "mathematics" not in str(path)


def test_due_reviews_come_first_then_practice_and_ready_topics_leave_the_path(monkeypatch):
    with TestClient(app) as client:
        owner, course, _, session = _study(client)
        _quiz(client, monkeypatch, owner, session, "paging", "Frames")
        _quiz(client, monkeypatch, owner, session, "deadlock", "Paging")
        path = _path(client, owner)
        assert [(s["title"], s["action"]) for s in path["steps"]] == [("Deadlock", "practise")]
        assert path["ready"] == 1

        _age(4)
        path = _path(client, owner, course)
        assert [(s["title"], s["action"]) for s in path["steps"]] == [
            ("Paging", "review"),
            ("Deadlock", "practise"),
        ]


def test_another_learners_course_is_not_found():
    with TestClient(app) as client:
        _, course, _, _ = _study(client)
        other = login_student(client)
        response = client.get(f"/api/v1/student/{other}/learning_path?course_id={course}")
        assert response.status_code == 404
        assert _path(client, other)["steps"] == []
