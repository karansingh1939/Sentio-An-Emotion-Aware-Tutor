"""Looking away, reported by the browser's attention telemetry, counts as a disengaged reading."""

import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from sentio.api.app import PREFIX, agent, app
from sentio.config import emotion_cfg, tutor_cfg
from tests.helpers import login_student

TELEMETRY = {
    "attention_score": 0.1,
    "focused": 0,
    "eye_openness": 0.7,
    "head_pose_pitch": 1.0,
    "head_pose_yaw": 40.0,
    "emotion": "focused",
}


def _session(client):
    owner = login_student(client)
    session_id = client.post(
        PREFIX + "/sessions",
        json={"student_id": owner, "subject": "physics", "topic": "Inertia"},
    ).json()["session_id"]
    return owner, session_id


def _consent(client, owner, allowed):
    response = client.post(
        PREFIX + f"/student/{owner}/consent",
        json={"consent_version": "camera-v1", "preferences": {"telemetry": allowed}},
    )
    assert response.status_code == 200


def _events(session_id):
    return agent.sm.get_session(session_id).emotion_timeline.recent(100)


def test_looking_away_records_a_confident_disengaged_reading():
    with patch.object(emotion_cfg, "ENABLED", True), TestClient(app) as client:
        owner, session_id = _session(client)
        _consent(client, owner, True)
        before = (
            agent.sm.get_session(session_id).difficulty,
            list(agent.sm.get_session(session_id).difficulty_log),
        )
        response = client.post(PREFIX + f"/sessions/{session_id}/telemetry", json=TELEMETRY)
        assert response.status_code == 200
        (event,) = _events(session_id)
        assert (event.emotion, event.learning_state, event.confidence) == (
            "looking_away",
            "disengaged",
            0.9,
        )
        assert event.confidence >= tutor_cfg.EMOTION_CONFIDENCE_THRESHOLD
        assert abs(event.timestamp - time.time()) < 60
        session = agent.sm.get_session(session_id)
        assert (session.difficulty, session.difficulty_log) == before


def test_only_clear_inattention_is_confident_enough_to_count():
    with patch.object(emotion_cfg, "ENABLED", True), TestClient(app) as client:
        owner, session_id = _session(client)
        _consent(client, owner, True)
        path = PREFIX + f"/sessions/{session_id}/telemetry"
        for score in (0.0, 0.3, 0.7):
            assert (
                client.post(path, json={**TELEMETRY, "attention_score": score}).status_code == 200
            )
        assert [e.confidence for e in _events(session_id)] == [1.0, 0.7, 0.3]
        counted = [
            e for e in _events(session_id) if e.confidence >= tutor_cfg.EMOTION_CONFIDENCE_THRESHOLD
        ]
        assert [e.confidence for e in counted] == [1.0, 0.7]


def test_looking_at_the_screen_records_nothing():
    with patch.object(emotion_cfg, "ENABLED", True), TestClient(app) as client:
        owner, session_id = _session(client)
        _consent(client, owner, True)
        body = {**TELEMETRY, "focused": 1, "attention_score": 0.9}
        assert (
            client.post(PREFIX + f"/sessions/{session_id}/telemetry", json=body).status_code == 200
        )
        assert _events(session_id) == []


def test_nothing_is_recorded_when_the_feature_is_off():
    assert emotion_cfg.ENABLED is False
    with TestClient(app) as client:
        owner, session_id = _session(client)
        _consent(client, owner, True)
        response = client.post(PREFIX + f"/sessions/{session_id}/telemetry", json=TELEMETRY)
        assert response.status_code == 404
        assert _events(session_id) == []


def test_nothing_is_recorded_without_consent():
    with patch.object(emotion_cfg, "ENABLED", True), TestClient(app) as client:
        owner, session_id = _session(client)
        path = PREFIX + f"/sessions/{session_id}/telemetry"
        assert client.post(path, json=TELEMETRY).status_code == 403
        _consent(client, owner, False)
        assert client.post(path, json=TELEMETRY).status_code == 403
        assert _events(session_id) == []
