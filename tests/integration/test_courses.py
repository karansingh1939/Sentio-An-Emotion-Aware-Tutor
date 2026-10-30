"""Courses group a student's lectures; a course session studies every lecture in it."""

import json
from io import BytesIO

from fastapi.testclient import TestClient
from pptx import Presentation
from sqlalchemy import text

from sentio.ai.grounding import NO_SOURCE
from sentio.ai.providers import OllamaBackend
from sentio.api.app import agent, app
from tests.helpers import login_student

SCHEDULING = b"Round robin scheduling gives each process a fixed time slice."
DEADLOCK = b"A deadlock needs mutual exclusion, hold and wait, no preemption and circular wait."


def _upload(client, name, content, course_id=None, mime="text/plain"):
    data = {"category": "notes", **({"course_id": course_id} if course_id else {})}
    return client.post("/api/v1/documents/upload", files={"file": (name, content, mime)}, data=data)


def _course(client, name="Operating Systems"):
    response = client.post("/api/v1/courses", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _session(client, owner, source):
    return client.post(
        "/api/v1/sessions",
        json={
            "student_id": owner,
            "subject": "OS",
            "topic": "Review",
            "metadata": {"document_id": source},
        },
    )


def _sources(stream):
    return json.loads(stream.split("event: sources\ndata: ")[1].split("\n")[0])["sources"]


def test_courses_are_created_renamed_listed_and_owner_scoped():
    with TestClient(app) as client:
        login_student(client)
        course = _course(client, "  Operating   Systems ")
        assert course["name"] == "Operating Systems"
        assert client.post("/api/v1/courses", json={"name": "operating systems"}).status_code == 409
        assert client.post("/api/v1/courses", json={"name": "   "}).status_code == 422
        renamed = client.patch(f"/api/v1/courses/{course['id']}", json={"name": "OS"})
        assert renamed.json()["name"] == "OS"
        assert [c["name"] for c in client.get("/api/v1/courses").json()["courses"]] == ["OS"]

        login_student(client)
        assert client.get("/api/v1/courses").json()["courses"] == []
        assert (
            client.patch(f"/api/v1/courses/{course['id']}", json={"name": "Mine"}).status_code
            == 404
        )
        assert client.delete(f"/api/v1/courses/{course['id']}").status_code == 404
        assert _upload(client, "x.txt", SCHEDULING, course["id"]).status_code == 404


def test_lectures_upload_into_move_between_and_survive_course_deletion():
    with TestClient(app) as client:
        login_student(client)
        os_course, db_course = _course(client), _course(client, "Databases")
        uploaded = _upload(client, "lecture1.txt", SCHEDULING, os_course["id"])
        assert uploaded.status_code == 201, uploaded.text
        document = uploaded.json()["document_id"]
        listed = {d["id"]: d for d in client.get("/api/v1/documents").json()["documents"]}
        assert listed[document]["course_id"] == os_course["id"]
        assert client.get("/api/v1/courses").json()["courses"][1]["lecture_count"] == 1

        moved = client.patch(
            f"/api/v1/documents/{document}/course", json={"course_id": db_course["id"]}
        )
        assert moved.status_code == 200
        # Re-uploading the same lecture keeps the course it was moved to.
        assert _upload(client, "lecture1.txt", SCHEDULING + b" Updated.").status_code == 201
        listed = {d["id"]: d for d in client.get("/api/v1/documents").json()["documents"]}
        assert listed[document]["course_id"] == db_course["id"]

        assert client.delete(f"/api/v1/courses/{db_course['id']}").json() == {"deleted": True}
        listed = {d["id"]: d for d in client.get("/api/v1/documents").json()["documents"]}
        assert listed[document]["course_id"] is None

        login_student(client)
        foreign = _course(client, "Theirs")
        login_student(client)
        assert (
            client.patch(
                f"/api/v1/documents/{document}/course", json={"course_id": foreign["id"]}
            ).status_code
            == 404
        )


def test_course_session_includes_lectures_added_after_it_started():
    with TestClient(app) as client:
        owner = login_student(client)
        course = _course(client)
        _upload(client, "scheduling.txt", SCHEDULING, course["id"])
        created = _session(client, owner, f"course:{course['id']}")
        assert created.status_code == 201, created.text
        session = created.json()["session_id"]
        _upload(client, "deadlock.txt", DEADLOCK, course["id"])
        stream = client.post(
            f"/api/v1/sessions/{session}/chat/stream",
            json={"message": "What conditions cause a deadlock?", "request_id": "course-1"},
        ).text
        assert "deadlock.txt" in {s["filename"] for s in _sources(stream)}

        quiz = client.post(
            "/api/v1/quizzes/generate",
            json={
                "student_id": owner,
                "session_id": session,
                "subject": "OS",
                "topic": "deadlock",
                "num_questions": 2,
            },
        )
        assert quiz.status_code == 200, quiz.text

        login_student(client)
        other = _session(client, owner, f"course:{course['id']}")
        assert other.status_code == 403


def test_old_sessions_without_notes_ask_for_notes_without_calling_the_model(monkeypatch):
    calls = []
    monkeypatch.setattr(OllamaBackend, "complete", lambda self, **kwargs: calls.append(kwargs))
    with TestClient(app) as client:
        owner = login_student(client)
        session = _session(client, owner, "none").json()["session_id"]
        stream = client.post(
            f"/api/v1/sessions/{session}/chat/stream",
            json={"message": "What is a process?", "request_id": "no-notes-1"},
        ).text
    assert NO_SOURCE in stream and calls == []


def test_powerpoint_lectures_are_cited_by_slide_and_old_ppt_is_explained():
    deck = Presentation()
    deck.slides.add_slide(deck.slide_layouts[6])
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = "Paging"
    slide.placeholders[1].text_frame.text = "Paging splits memory into fixed size frames."
    buffer = BytesIO()
    deck.save(buffer)
    with TestClient(app) as client:
        owner = login_student(client)
        mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        uploaded = _upload(client, "memory.pptx", buffer.getvalue(), mime=mime)
        assert uploaded.status_code == 201, uploaded.text
        session = _session(client, owner, uploaded.json()["document_id"]).json()["session_id"]
        stream = client.post(
            f"/api/v1/sessions/{session}/chat/stream",
            json={"message": "How does paging split memory?", "request_id": "pptx-slide-1"},
        ).text
        assert {(s["filename"], s["page"]) for s in _sources(stream)} == {("memory.pptx", 2)}

        legacy = _upload(client, "old.ppt", b"binary", mime="application/vnd.ms-powerpoint")
        assert legacy.status_code == 400 and ".pptx" in legacy.json()["detail"]


def test_courses_are_exported_and_removed_with_the_account():
    with TestClient(app) as client:
        owner = login_student(client)
        _course(client, "Compilers")
        exported = client.get(f"/api/v1/student/{owner}/export").json()["data"]
        assert [c["name"] for c in exported["courses"]] == ["Compilers"]
        assert client.delete(f"/api/v1/student/{owner}/data").status_code == 200
    with agent.sm.persister._engine.connect() as connection:
        remaining = connection.execute(
            text("SELECT COUNT(*) FROM courses WHERE student_id=:owner"), {"owner": owner}
        ).scalar()
    assert remaining == 0
