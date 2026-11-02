"""Studying a lecture slide by slide: slides, the current slide, session mode and study mood."""

from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pptx import Presentation

from sentio.api.app import PREFIX, agent, app
from sentio.config import emotion_cfg
from sentio.session.models import EmotionEvent
from tests.helpers import login_student

SLIDES = [
    ("Paging", "Paging splits memory into fixed size frames."),
    ("Paging (cont.)", "A page table maps each page to a frame."),
    ("Deadlock", "Deadlock needs circular wait and hold and wait."),
]
MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _deck(slides=SLIDES):
    deck = Presentation()
    for title, body in slides:
        slide = deck.slides.add_slide(deck.slide_layouts[1])
        slide.shapes.title.text = title
        slide.placeholders[1].text_frame.text = body
    buffer = BytesIO()
    deck.save(buffer)
    return buffer.getvalue()


def _upload(client, name="memory.pptx", **data):
    response = client.post(
        PREFIX + "/documents/upload",
        files={"file": (name, _deck(), MIME)},
        data={"category": "notes", **data},
    )
    assert response.status_code == 201, response.text
    return response.json()["document_id"]


def _session(client, owner, metadata):
    return client.post(
        PREFIX + "/sessions",
        json={"student_id": owner, "topic": "Review", "metadata": metadata},
    )


def _study(client):
    owner = login_student(client)
    document = _upload(client)
    session = _session(client, owner, {"document_id": document, "mode": "slides"})
    assert session.status_code == 201, session.text
    return owner, document, session.json()["session_id"]


def _consent(client, owner, allowed):
    response = client.post(
        PREFIX + f"/student/{owner}/consent",
        json={"consent_version": "camera-v1", "preferences": {"telemetry": allowed}},
    )
    assert response.status_code == 200


def test_slides_of_a_deck_have_titles_and_topics():
    with TestClient(app) as client:
        _, document, _ = _study(client)
        topics = client.get(PREFIX + f"/documents/{document}/topics").json()["topics"]
        lecture = client.get(PREFIX + f"/documents/{document}/slides")
        assert lecture.status_code == 200
        lecture = lecture.json()
        assert lecture["document_id"] == document
        assert lecture["filename"] == "memory.pptx"
        slides = lecture["slides"]
        assert [s["number"] for s in slides] == [1, 2, 3]
        # A slide that starts a topic carries the topic's heading; the others their first line.
        assert [s["title"] for s in slides] == ["Paging", "Paging (cont.)", "Deadlock"]
        assert [s["topic_title"] for s in slides] == ["Paging", "Paging", "Deadlock"]
        assert [s["topic_id"] for s in slides] == [
            topics[0]["id"],
            topics[0]["id"],
            topics[1]["id"],
        ]
        assert "Paging splits memory" in slides[0]["text"]


def test_a_long_first_line_is_trimmed_to_120_characters():
    with TestClient(app) as client:
        login_student(client)
        long_line = "word " * 60
        deck = _deck([SLIDES[0], (long_line.strip(), "Body text.")])
        document = client.post(
            PREFIX + "/documents/upload",
            files={"file": ("long.pptx", deck, MIME)},
            data={"category": "notes"},
        ).json()["document_id"]
        slides = client.get(PREFIX + f"/documents/{document}/slides").json()["slides"]
        assert [s["title"] for s in slides] == ["Paging", long_line.strip()[:120]]
        assert slides[1]["topic_title"] == "Paging"  # A long line is no heading.


def test_slides_are_private_to_their_owner_and_missing_notes_are_404():
    with TestClient(app) as client:
        _, document, _ = _study(client)
        assert client.get(PREFIX + f"/documents/{document}/slides").status_code == 200
        client.headers.pop("Authorization")
        login_student(client)
        assert client.get(PREFIX + f"/documents/{document}/slides").status_code == 404
        assert client.get(PREFIX + "/documents/missing/slides").status_code == 404


def test_the_studied_slide_is_saved_on_the_session():
    with TestClient(app) as client:
        _, _, session = _study(client)
        path = PREFIX + f"/sessions/{session}/slide"
        assert client.put(path, json={"number": 2}).json() == {"number": 2}
        assert agent.sm.get_session(session).metadata["slide"] == 2
        assert client.put(path, json={"number": 4}).status_code == 404
        assert client.put(path, json={"number": 0}).status_code == 404
        assert client.put(path, json={"number": "x"}).status_code == 422
        assert agent.sm.get_session(session).metadata["slide"] == 2


def test_the_slide_is_kept_when_saving_fails():
    with TestClient(app) as client:
        _, _, session = _study(client)
        path = PREFIX + f"/sessions/{session}/slide"
        assert client.put(path, json={"number": 1}).status_code == 200
        with patch.object(agent.sm.persister, "save_session", side_effect=RuntimeError("disk")):
            assert client.put(path, json={"number": 3}).status_code == 503
        assert agent.sm.get_session(session).metadata["slide"] == 1


def test_only_the_owner_sets_the_slide():
    with TestClient(app) as client:
        _, _, session = _study(client)
        client.headers.pop("Authorization")
        login_student(client)
        response = client.put(PREFIX + f"/sessions/{session}/slide", json={"number": 1})
        assert response.status_code == 403


def test_a_session_on_all_notes_a_course_or_a_list_has_no_slide():
    with TestClient(app) as client:
        owner = login_student(client)
        document = _upload(client)
        course = client.post(PREFIX + "/courses", json={"name": "Operating Systems"}).json()
        for source in ("all", f"course:{course['id']}", [document]):
            session = _session(client, owner, {"document_id": source}).json()["session_id"]
            response = client.put(PREFIX + f"/sessions/{session}/slide", json={"number": 1})
            assert response.status_code == 409, source
        without_notes = _session(client, owner, {}).json()["session_id"]
        assert (
            client.put(PREFIX + f"/sessions/{without_notes}/slide", json={"number": 1}).status_code
            == 409
        )


def test_session_mode_is_validated_when_it_is_created():
    with TestClient(app) as client:
        owner = login_student(client)
        document = _upload(client)
        course = client.post(PREFIX + "/courses", json={"name": "Operating Systems"}).json()
        ok = _session(client, owner, {"document_id": document, "mode": "slides"})
        assert ok.status_code == 201
        assert _session(client, owner, {"document_id": document}).status_code == 201
        for metadata in (
            {"document_id": document, "mode": "flashcards"},
            {"document_id": document, "mode": ["slides"]},
            {"mode": "slides"},
            {"document_id": "all", "mode": "slides"},
            {"document_id": f"course:{course['id']}", "mode": "slides"},
            {"document_id": [document], "mode": "slides"},
            {"document_id": "not-my-document", "mode": "slides"},
        ):
            response = _session(client, owner, metadata)
            assert response.status_code == 422, metadata
        client.headers.pop("Authorization")
        other = login_student(client)
        assert (
            _session(client, other, {"document_id": document, "mode": "slides"}).status_code == 422
        )


def test_changing_notes_clears_the_slide_and_mode():
    with TestClient(app) as client:
        owner, document, session = _study(client)
        client.put(PREFIX + f"/sessions/{session}/slide", json={"number": 2})
        assert agent.sm.get_session(session).metadata["slide"] == 2
        path = PREFIX + f"/sessions/{session}/grounding"
        with patch.object(agent.sm.persister, "save_session", side_effect=RuntimeError("disk")):
            assert client.post(path, json={"document_id": "all"}).status_code == 503
        metadata = agent.sm.get_session(session).metadata
        assert (metadata["document_id"], metadata["slide"], metadata["mode"]) == (
            document,
            2,
            "slides",
        )
        assert client.post(path, json={"document_id": "all"}).status_code == 200
        metadata = agent.sm.get_session(session).metadata
        assert metadata["document_id"] == "all"
        assert "slide" not in metadata and "mode" not in metadata


def test_mood_is_hidden_when_the_camera_feature_is_off():
    assert emotion_cfg.ENABLED is False
    with TestClient(app) as client:
        owner, _, session = _study(client)
        _consent(client, owner, True)
        assert client.get(PREFIX + f"/sessions/{session}/mood").status_code == 404


def test_mood_needs_consent_and_a_session_of_your_own():
    with patch.object(emotion_cfg, "ENABLED", True), TestClient(app) as client:
        owner, _, session = _study(client)
        path = PREFIX + f"/sessions/{session}/mood"
        assert client.get(path).status_code == 403
        _consent(client, owner, True)
        assert client.get(path).status_code == 200
        _consent(client, owner, False)
        assert client.get(path).status_code == 403
        client.headers.pop("Authorization")
        login_student(client)
        assert client.get(path).status_code == 403


@pytest.mark.parametrize(
    "state,label",
    [
        ("engaged", "focused"),
        ("curious", "focused"),
        ("struggling", "unsure"),
        ("frustrated", "unsure"),
        ("anxious", "unsure"),
        ("disengaged", "distracted"),
        ("neutral", "calm"),
    ],
)
def test_mood_gets_a_plain_label_from_the_study_mood(monkeypatch, state, label):
    calls = []

    def study_mood(events, now):
        calls.append((list(events), now))
        return {
            "learning_state": state,
            "confidence": 0.8,
            "since": 100.0,
            "nudge": "simpler" if state == "struggling" else None,
            "fresh": True,
        }

    monkeypatch.setattr("sentio.emotion.policy.study_mood", study_mood)
    with patch.object(emotion_cfg, "ENABLED", True), TestClient(app) as client:
        owner, _, session = _study(client)
        _consent(client, owner, True)
        timeline = agent.sm.get_session(session).emotion_timeline
        timeline.record(EmotionEvent(10.0, "sad", "struggling", 0.7, "simplify"))
        timeline.record(EmotionEvent(20.0, "happy", "engaged", 0.9, "challenge"))
        response = client.get(PREFIX + f"/sessions/{session}/mood")
        assert response.status_code == 200
        assert response.json() == {
            "learning_state": state,
            "confidence": 0.8,
            "since": 100.0,
            "nudge": "simpler" if state == "struggling" else None,
            "fresh": True,
            "label": label,
        }
        events, now = calls[0]
        assert [e.timestamp for e in events] == [10.0, 20.0]  # Oldest first.
        assert now > 1_000_000_000
