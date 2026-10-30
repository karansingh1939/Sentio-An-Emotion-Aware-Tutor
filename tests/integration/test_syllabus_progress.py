"""A course syllabus is matched to lecture topics and shows how much of it is ready."""

from io import BytesIO

import docx
from fastapi.testclient import TestClient

from sentio.api.app import app
from tests.helpers import login_student
from tests.integration.test_topic_mastery import _quiz, _study

SYLLABUS = """Unit 1: Memory – Paging, Virtual memory
Unit 2: Synchronisation – Deadlocks, Semaphores
Text Books:
1. Operating System Concepts
"""


def _items(progress):
    return {item["title"]: item["status"] for item in progress["items"]}


def test_syllabus_matches_lectures_and_tracks_readiness(monkeypatch):
    with TestClient(app) as client:
        owner, course, _, session = _study(client)
        saved = client.put(f"/api/v1/courses/{course}/syllabus", data={"text": SYLLABUS})
        assert saved.status_code == 200, saved.text
        progress = saved.json()
        assert [(i["unit"], i["title"]) for i in progress["items"]] == [
            ("Unit 1: Memory", "Paging"),
            ("Unit 1: Memory", "Virtual memory"),
            ("Unit 2: Synchronisation", "Deadlocks"),
            ("Unit 2: Synchronisation", "Semaphores"),
        ]
        assert _items(progress) == {
            "Paging": "not_started",
            "Virtual memory": "no_notes",
            "Deadlocks": "not_started",
            "Semaphores": "no_notes",
        }
        paging = progress["items"][0]["topics"][0]
        assert (paging["title"], paging["first_page"], paging["last_page"]) == ("Paging", 1, 2)

        _quiz(client, monkeypatch, owner, session, "paging", "Frames")
        _quiz(client, monkeypatch, owner, session, "paging", "Frames")
        progress = client.get(f"/api/v1/courses/{course}/syllabus").json()
        assert _items(progress)["Paging"] == "ready"
        assert progress["summary"] == {
            "ready": 1,
            "practising": 0,
            "not_started": 1,
            "no_notes": 2,
            "total": 4,
            "percent_ready": 25,
        }

        # A lecture added later is matched automatically.
        client.post(
            "/api/v1/documents/upload",
            files={"file": ("sync.txt", b"Semaphores protect a critical section.", "text/plain")},
            data={"category": "notes", "course_id": course},
        )
        assert _items(client.get(f"/api/v1/courses/{course}/syllabus").json())["Semaphores"] == (
            "not_started"
        )


def test_matches_can_be_corrected_and_reset(monkeypatch):
    with TestClient(app) as client:
        owner, course, _, session = _study(client)
        progress = client.put(f"/api/v1/courses/{course}/syllabus", data={"text": SYLLABUS}).json()
        virtual, paging = progress["items"][1], progress["items"][0]
        paging_topic = paging["topics"][0]["id"]
        _quiz(client, monkeypatch, owner, session, "paging", "Frames")
        _quiz(client, monkeypatch, owner, session, "paging", "Frames")

        manual = client.patch(
            f"/api/v1/syllabus/{virtual['id']}", json={"mode": "manual", "topic_id": paging_topic}
        )
        assert manual.status_code == 200
        assert (
            client.patch(f"/api/v1/syllabus/{paging['id']}", json={"mode": "none"}).status_code
            == 200
        )
        statuses = _items(client.get(f"/api/v1/courses/{course}/syllabus").json())
        assert (statuses["Virtual memory"], statuses["Paging"]) == ("ready", "no_notes")

        client.patch(f"/api/v1/syllabus/{paging['id']}", json={"mode": "auto"})
        assert _items(client.get(f"/api/v1/courses/{course}/syllabus").json())["Paging"] == "ready"
        assert (
            client.patch(f"/api/v1/syllabus/{paging['id']}", json={"mode": "manual"}).status_code
            == 422
        )

        login_student(client)
        assert client.get(f"/api/v1/courses/{course}/syllabus").status_code == 404
        assert (
            client.put(f"/api/v1/courses/{course}/syllabus", data={"text": SYLLABUS}).status_code
            == 404
        )
        assert (
            client.patch(f"/api/v1/syllabus/{paging['id']}", json={"mode": "none"}).status_code
            == 404
        )


def test_syllabus_files_are_read_and_unreadable_ones_explained():
    document = docx.Document()
    for line in ["Module 1 - Paging, Segmentation", "Module 2 - Deadlocks"]:
        document.add_paragraph(line)
    buffer = BytesIO()
    document.save(buffer)
    with TestClient(app) as client:
        owner, course, _, _ = _study(client)
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        saved = client.put(
            f"/api/v1/courses/{course}/syllabus",
            files={"file": ("syllabus.docx", buffer.getvalue(), mime)},
        )
        assert saved.status_code == 200, saved.text
        assert [i["title"] for i in saved.json()["items"]] == [
            "Paging",
            "Segmentation",
            "Deadlocks",
        ]

        assert (
            client.put(
                f"/api/v1/courses/{course}/syllabus", files={"file": ("s.xlsx", b"x", "text/plain")}
            ).status_code
            == 400
        )
        assert (
            client.put(f"/api/v1/courses/{course}/syllabus", data={"text": "  "}).status_code == 422
        )

        exported = client.get(f"/api/v1/student/{owner}/export").json()["data"]
        assert [i["title"] for i in exported["syllabus_items"]] == [
            "Paging",
            "Segmentation",
            "Deadlocks",
        ]
        assert client.delete(f"/api/v1/courses/{course}/syllabus").json() == {"deleted": True}
        assert client.get(f"/api/v1/courses/{course}/syllabus").json()["items"] == []
