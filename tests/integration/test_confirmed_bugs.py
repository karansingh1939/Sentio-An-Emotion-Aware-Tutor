"""Regressions for bugs confirmed by the feature review of 30 October 2026."""

import json
import time

from fastapi.testclient import TestClient

from sentio.api.app import app
from sentio.intelligence.service import study_streak
from tests.helpers import login_student

PHYSICS = b"Inertia resists changes in velocity. A net force changes velocity."
HISTORY = b"The Magna Carta was sealed by King John at Runnymede in 1215."
DAY = 86400


def _upload(client, name, text, subject):
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": (name, text, "text/plain")},
        data={"subject": subject},
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["document_id"]


def test_search_all_notes_includes_notes_filed_under_another_subject():
    with TestClient(app) as client:
        owner = login_student(client)
        _upload(client, "physics.txt", PHYSICS, "physics")
        _upload(client, "history.txt", HISTORY, "history")
        session = client.post(
            "/api/v1/sessions",
            json={
                "student_id": owner,
                "subject": "physics",
                "topic": "Review",
                "metadata": {"document_id": "all"},
            },
        ).json()["session_id"]
        stream = client.post(
            f"/api/v1/sessions/{session}/chat/stream",
            json={"message": "Who sealed the Magna Carta?", "request_id": "all-notes-1"},
        ).text
    sources = json.loads(stream.split("event: sources\ndata: ")[1].split("\n")[0])["sources"]
    assert "history.txt" in {source["filename"] for source in sources}


def test_study_streak_counts_consecutive_days_not_sessions():
    now = time.mktime((2026, 10, 30, 12, 0, 0, 0, 0, -1))
    assert study_streak([now, now - 60, now - 120], now) == 1
    assert study_streak([now, now - DAY, now - 2 * DAY, now - 4 * DAY], now) == 3
    assert study_streak([now - DAY, now - 2 * DAY], now) == 2
    assert study_streak([now - 3 * DAY], now) == 0
    assert study_streak([], now) == 0
