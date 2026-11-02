"""Slide study explains the slide first, and a fresh camera mood changes only the tone."""

import json
import time

from fastapi.testclient import TestClient

from sentio.ai.providers import OllamaBackend
from sentio.api.app import agent, app
from sentio.rag.knowledge_base import ContentAdapter
from sentio.repositories.slides import SlideRepository
from sentio.session.models import EmotionEvent
from sentio.tutor.slides import SLIDE_INSTRUCTION
from tests.integration.test_topic_mastery import _study

QUESTION = "What does a page table map?"
SIMPLE_TONE = ContentAdapter.STRATEGY_TONE["simplify"]
STANDARD_TONE = ContentAdapter.STRATEGY_TONE["standard"]


def _slide(document, number=1):
    return {
        "number": number,
        "title": "Paging",
        "text": "Paging splits memory into fixed size frames.",
        "topic_id": None,
        "topic_title": "Paging",
        "filename": "memory.pptx",
        "document_id": document,
    }


def _model(monkeypatch, prompts):
    def provider(self, system_prompt, history, user_message, **kwargs):
        prompts.append((system_prompt, json.loads(user_message)))
        answer = "Paging splits memory into frames [memory.pptx Page 1]."
        return json.dumps({"text": answer}), 20

    monkeypatch.setattr(OllamaBackend, "complete", provider)


def _slides(monkeypatch, slide):
    calls = []

    def lookup(self, owner, document_id, number):
        calls.append((document_id, number))
        return slide

    monkeypatch.setattr(SlideRepository, "slide", lookup)
    return calls


def _ask(client, session, request_id, message=QUESTION):
    stream = client.post(
        f"/api/v1/sessions/{session}/chat/stream",
        json={"message": message, "request_id": request_id},
    ).text
    assert "event: complete" in stream, stream
    return stream


def _slide_mode(session, number=1):
    agent.sm.get_session(session).metadata.update(mode="slides", slide=number)


def _camera(session, state, seconds_ago):
    """A steady camera reading of a state for ten seconds, ending `seconds_ago`."""
    timeline = agent.sm.get_session(session).emotion_timeline
    now = time.time()
    for at in range(seconds_ago + 10, seconds_ago - 1, -1):
        timeline.record(EmotionEvent(now - at, state, state, 0.9, "standard"))


def test_slide_mode_explains_the_slide_first_with_nearby_passages(monkeypatch):
    with TestClient(app) as client:
        _, _, document, session = _study(client)
        _slide_mode(session)
        calls = _slides(monkeypatch, _slide(document))
        prompts = []
        _model(monkeypatch, prompts)
        stream = _ask(client, session, "slide-first")

        assert calls == [(document, 1)]
        system, data = prompts[0]
        assert system.endswith(SLIDE_INSTRUCTION)
        passages = data["source_passages"]
        assert (passages[0]["page"], passages[0]["reference"]) == (1, "[memory.pptx Page 1]")
        assert passages[0]["text"] == "Paging splits memory into fixed size frames."
        assert any("A page table maps" in p["text"] for p in passages[1:])
        assert all(p["filename"] == "memory.pptx" and p["page"] != 1 for p in passages[1:])
        assert "[memory.pptx Page 1]" in stream


def test_a_missing_slide_falls_back_to_normal_retrieval(monkeypatch):
    with TestClient(app) as client:
        _, _, document, session = _study(client)
        _slide_mode(session, 99)
        calls = _slides(monkeypatch, None)
        prompts = []
        _model(monkeypatch, prompts)
        _ask(client, session, "slide-missing")

        assert calls == [(document, 99)]
        system, data = prompts[0]
        assert SLIDE_INSTRUCTION not in system
        assert data["source_passages"][0]["page"] == 2


def test_normal_sessions_are_unchanged(monkeypatch):
    with TestClient(app) as client:
        _, _, _, session = _study(client)
        agent.sm.get_session(session).metadata["slide"] = 1  # Without slide mode.
        calls = _slides(monkeypatch, None)
        prompts = []
        _model(monkeypatch, prompts)
        _ask(client, session, "normal-1")

        assert calls == []
        system, data = prompts[0]
        assert SLIDE_INSTRUCTION not in system
        assert data["session"]["tone"] == STANDARD_TONE
        assert data["source_passages"][0]["page"] == 2


def _camera_turns(client, monkeypatch, seconds_ago):
    """A turn without the camera, then camera readings, then the same question again."""
    _, _, _, session = _study(client)
    prompts = []
    _model(monkeypatch, prompts)
    _ask(client, session, "before-camera")
    _camera(session, "struggling", seconds_ago)
    _ask(client, session, "with-camera")
    return agent.sm.get_session(session), prompts[0][1], prompts[1][1]


def test_a_fresh_camera_mood_changes_only_the_tone(monkeypatch):
    with TestClient(app) as client:
        session, before, after = _camera_turns(client, monkeypatch, 0)

        assert before["session"]["tone"] == STANDARD_TONE
        assert after["session"]["tone"] == SIMPLE_TONE
        assert {**after["session"], "tone": None} == {**before["session"], "tone": None}
        assert after["source_passages"] == before["source_passages"]
        assert session.metadata["learning_state"] == "neutral"


def test_what_the_student_asks_for_beats_the_cameras_guess(monkeypatch):
    with TestClient(app) as client:
        _, _, _, session = _study(client)
        prompts = []
        _model(monkeypatch, prompts)
        _camera(session, "struggling", 0)
        _ask(client, session, "asks-harder", "Can you make it harder? " + QUESTION)

        assert prompts[0][1]["session"]["tone"] == ContentAdapter.STRATEGY_TONE["challenge"]


def test_a_stale_camera_mood_keeps_todays_tone(monkeypatch):
    with TestClient(app) as client:
        _, before, after = _camera_turns(client, monkeypatch, 120)

        assert after["session"] == before["session"]
        assert after["session"]["tone"] == STANDARD_TONE
