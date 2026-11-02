"""Phase 4: study a lecture slide by slide, with an optional camera mood that changes tone only.

Written against docs/project/phase-4-slide-study.md. Where the contract is silent the
assumption is marked "ASSUMPTION" and listed in the QA report.
"""

import json
import time
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from sentio.ai.providers import OllamaBackend
from sentio.api.app import PREFIX, agent, app
from sentio.config import emotion_cfg
from sentio.session.models import EmotionEvent
from tests.helpers import complete, login_student
from tests.integration.test_topic_mastery import SLIDES, _deck

PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
# ASSUMPTION: "sustained" is no longer than this. MOOD_WINDOW_SEC (30) bounds freshness, so a
# state that began 25 seconds ago and is still being read now is both fresh and sustained.
SUSTAINED_SEC = 25


@pytest.fixture
def prompts(monkeypatch):
    """Capture every model call; answer grounded questions by citing the first passage."""
    calls = []

    def recording(self, system_prompt, history, user_message, **kwargs):
        calls.append(SimpleNamespace(system=system_prompt, user=user_message))
        try:
            passages = json.loads(user_message).get("source_passages") or []
        except ValueError:
            passages = []
        if passages:
            return json.dumps({"text": f"This slide explains it {passages[0]['reference']}."}), 20
        return complete(system_prompt, history, user_message, **kwargs)

    monkeypatch.setattr(OllamaBackend, "complete", recording)
    return calls


def _passages(call):
    """ASSUMPTION: passages reach the model in the JSON user message ("source_passages"),
    as PromptBuilder does today, in citation order (Citation Index 1 first)."""
    return json.loads(call.user)["source_passages"]


def _has(call, text):
    """True if the prompt (system or user message, raw or JSON-escaped) carries the text."""
    escaped = json.dumps(text, ensure_ascii=False)[1:-1]
    return any(text in part or escaped in part for part in (call.system, call.user))


def _study_slides(client):
    owner = login_student(client)
    document = client.post(
        PREFIX + "/documents/upload",
        files={"file": ("memory.pptx", _deck(), PPTX)},
        data={"category": "notes"},
    ).json()["document_id"]
    session = client.post(
        PREFIX + "/sessions",
        json={
            "student_id": owner,
            "subject": "Operating Systems",
            "topic": "Slides",
            "metadata": {"document_id": document, "mode": "slides"},
        },
    )
    assert session.status_code in (200, 201), session.text
    return owner, document, session.json()["session_id"]


def _ask(client, session, message):
    response = client.post(
        PREFIX + f"/sessions/{session}/chat/stream",
        json={"request_id": "slide-" + uuid.uuid4().hex, "message": message},
    )
    assert response.status_code == 200, response.text
    assert "event: complete" in response.text, response.text
    data = response.text.split("event: complete\ndata: ", 1)[1].split("\n", 1)[0]
    return json.loads(data)


def _consent(client, owner, allowed=True):
    response = client.post(
        PREFIX + f"/student/{owner}/consent",
        json={"consent_version": "camera-v1", "preferences": {"telemetry": allowed}},
    )
    assert response.status_code == 200, response.text


def _struggle(session_id, seconds=SUSTAINED_SEC):
    """Confusion read once a second up to now, as a camera would send it."""
    now = time.time()
    timeline = agent.sm.get_or_raise(session_id).emotion_timeline
    for offset in range(int(seconds), -1, -1):
        timeline.record(EmotionEvent(now - offset, "sad", "struggling", 0.9, "simplify"))


def test_slides_are_listed_in_order_for_the_owner_only(prompts):
    with TestClient(app) as client:
        _, document, _ = _study_slides(client)
        listing = client.get(PREFIX + f"/documents/{document}/slides")
        assert listing.status_code == 200, listing.text
        body = listing.json()
        assert body["document_id"] == document
        assert body["filename"] == "memory.pptx"
        assert [slide["number"] for slide in body["slides"]] == [1, 2, 3]
        assert SLIDES[1][1] in body["slides"][1]["text"]
        assert body["slides"][0]["title"] == "Paging"  # the slide that starts the Paging topic
        assert body["slides"][0]["topic_title"] == "Paging"
        assert body["slides"][1]["topic_title"] == "Paging"  # slide 2 continues that topic
        assert body["slides"][2]["topic_title"] == "Deadlock"

        login_student(client)
        assert client.get(PREFIX + f"/documents/{document}/slides").status_code == 404
        assert client.get(PREFIX + "/documents/not-a-document/slides").status_code == 404


def test_choosing_a_slide_is_stored_validated_and_cleared_with_the_notes(prompts):
    with TestClient(app) as client:
        owner, document, session = _study_slides(client)
        put = client.put(PREFIX + f"/sessions/{session}/slide", json={"number": 2})
        assert put.status_code == 200, put.text
        assert put.json() == {"number": 2}
        assert agent.sm.get_or_raise(session).metadata["slide"] == 2
        assert (
            client.put(PREFIX + f"/sessions/{session}/slide", json={"number": 9}).status_code == 404
        )

        # 409 unless the session studies one document (here: none, then a whole library).
        general = client.post(
            PREFIX + "/sessions", json={"student_id": owner, "subject": "x", "topic": "y"}
        ).json()["session_id"]
        assert (
            client.put(PREFIX + f"/sessions/{general}/slide", json={"number": 1}).status_code == 409
        )

        # Changing notes clears the slide and the mode.
        other = client.post(
            PREFIX + "/documents/upload",
            files={"file": ("other.txt", b"Caches keep recently used data close.", "text/plain")},
        ).json()["document_id"]
        changed = client.post(
            PREFIX + f"/sessions/{session}/grounding", json={"document_id": other}
        )
        assert changed.status_code == 200, changed.text
        metadata = agent.sm.get_or_raise(session).metadata
        assert "slide" not in metadata and "mode" not in metadata

        # Someone else's session is not reachable.
        stranger = login_student(client)
        assert stranger != owner
        assert client.put(
            PREFIX + f"/sessions/{session}/slide", json={"number": 1}
        ).status_code in (
            403,
            404,
        )


def test_explain_this_slide_starts_from_the_current_slide(prompts):
    with TestClient(app) as client:
        _, document, session = _study_slides(client)
        assert (
            client.put(PREFIX + f"/sessions/{session}/slide", json={"number": 2}).status_code == 200
        )

        result = _ask(client, session, "Explain this slide.")

        assert len(prompts) == 1
        passages = _passages(prompts[0])
        assert passages[0]["page"] == 2  # Citation Index 1 is the current slide
        assert passages[0]["filename"] == "memory.pptx"
        assert SLIDES[1][1] in passages[0]["text"]
        assert result["source_citations"][0]["page"] == 2
        assert "[memory.pptx Page 2]" in result["text"]
        # Nearby passages may follow the slide (at most 3 more), never replace it.
        assert 1 <= len(passages) <= 4


def test_a_follow_up_stays_on_the_slide_and_moving_on_changes_it(prompts):
    with TestClient(app) as client:
        _, _, session = _study_slides(client)
        client.put(PREFIX + f"/sessions/{session}/slide", json={"number": 1})
        _ask(client, session, "What is a frame?")
        client.put(PREFIX + f"/sessions/{session}/slide", json={"number": 3})
        result = _ask(client, session, "Explain this slide.")
        assert [_passages(call)[0]["page"] for call in prompts] == [1, 3]
        assert result["source_citations"][0]["page"] == 3


def test_mood_is_404_when_the_camera_feature_is_off(prompts):
    assert emotion_cfg.ENABLED is False
    with TestClient(app) as client:
        owner, _, session = _study_slides(client)
        _consent(client, owner)
        assert client.get(PREFIX + f"/sessions/{session}/mood").status_code == 404
        # Slide study itself is unaffected by the camera feature being off.
        client.put(PREFIX + f"/sessions/{session}/slide", json={"number": 1})
        assert _ask(client, session, "Explain this slide.")["source_citations"][0]["page"] == 1


def test_mood_needs_consent_and_is_scoped_to_the_owner(prompts):
    with patch.object(emotion_cfg, "ENABLED", True), TestClient(app) as client:
        owner, _, session = _study_slides(client)
        path = PREFIX + f"/sessions/{session}/mood"
        assert client.get(path).status_code == 403  # enabled, but no consent yet
        _consent(client, owner, True)
        assert client.get(path).status_code == 200
        _consent(client, owner, False)  # consent withdrawn: camera data is blocked again
        assert client.get(path).status_code == 403
        login_student(client)
        assert client.get(path).status_code in (403, 404)


def test_without_camera_readings_the_mood_has_no_label_and_no_nudge(prompts):
    with patch.object(emotion_cfg, "ENABLED", True), TestClient(app) as client:
        owner, _, session = _study_slides(client)
        _consent(client, owner)
        mood = client.get(PREFIX + f"/sessions/{session}/mood").json()
        assert mood["fresh"] is False
        assert mood["learning_state"] == "neutral"
        assert mood["nudge"] is None
        assert mood["label"] is None  # No fresh reading: the chip has nothing to say.


def test_sustained_confusion_offers_a_simpler_explanation_and_only_changes_the_tone(prompts):
    kb = agent.kb
    with patch.object(emotion_cfg, "ENABLED", True), TestClient(app) as client:
        owner, _, session = _study_slides(client)
        _consent(client, owner)
        client.put(PREFIX + f"/sessions/{session}/slide", json={"number": 2})
        difficulty = agent.sm.get_or_raise(session).difficulty

        _ask(client, session, "Explain this slide.")
        calm, struggling = kb.get_tone_instruction("neutral"), kb.get_tone_instruction("struggling")
        assert calm != struggling
        assert _has(prompts[0], calm) and not _has(prompts[0], struggling)

        _struggle(session)
        mood = client.get(PREFIX + f"/sessions/{session}/mood")
        assert mood.status_code == 200, mood.text
        mood = mood.json()
        assert mood["label"] == "unsure"
        assert mood["nudge"] == "simpler"
        assert mood["learning_state"] == "struggling"
        assert mood["fresh"] is True
        assert 0 < mood["confidence"] <= 1
        assert mood["since"] is not None

        result = _ask(client, session, "Explain this slide more simply.")

        # Tone follows the camera's reading, and nothing else changes.
        assert _has(prompts[1], struggling) and not _has(prompts[1], calm)
        assert _passages(prompts[1])[0]["page"] == 2
        assert result["source_citations"][0]["page"] == 2
        assert agent.sm.get_or_raise(session).difficulty == difficulty
        assert "difficulty_change" not in result


def test_a_stale_reading_is_not_shown_as_the_current_mood(prompts):
    with patch.object(emotion_cfg, "ENABLED", True), TestClient(app) as client:
        owner, _, session = _study_slides(client)
        _consent(client, owner)
        client.put(PREFIX + f"/sessions/{session}/slide", json={"number": 2})
        long_ago = time.time() - 600
        timeline = agent.sm.get_or_raise(session).emotion_timeline
        for offset in range(SUSTAINED_SEC):
            timeline.record(EmotionEvent(long_ago + offset, "sad", "struggling", 0.9, "simplify"))

        mood = client.get(PREFIX + f"/sessions/{session}/mood").json()
        assert mood["fresh"] is False
        assert mood["learning_state"] == "neutral"
        assert mood["nudge"] is None
        assert mood["label"] is None
        # Slide study still works with only stale readings.
        _ask(client, session, "Explain this slide.")
        assert _passages(prompts[0])[0]["page"] == 2


def _tone(session):
    return agent.orchestrator._tone_state({"session_id": session, "learning_state": "neutral"})


def test_the_camera_sets_the_tone_only_while_the_feature_is_on_and_consent_is_current(prompts):
    with TestClient(app) as client:
        owner, _, session = _study_slides(client)
        _consent(client, owner, True)
        _struggle(session)
        assert _tone(session) == "neutral"  # The feature is off: readings are ignored.

        with patch.object(emotion_cfg, "ENABLED", True):
            assert _tone(session) == "struggling"
            _consent(client, owner, False)
            # Withdrawing consent clears what the camera had seen, and later readings are
            # ignored too.
            assert len(agent.sm.get_or_raise(session).emotion_timeline) == 0
            assert _tone(session) == "neutral"
            _struggle(session)
            assert _tone(session) == "neutral"
            _consent(client, owner, True)
            assert _tone(session) == "struggling"


def test_a_student_who_never_consented_gets_no_camera_tone(prompts):
    with patch.object(emotion_cfg, "ENABLED", True), TestClient(app) as client:
        _, _, session = _study_slides(client)
        _struggle(session)
        assert _tone(session) == "neutral"
