"""Camera history is exportable and deletable, and the live frame stream is rate limited."""

import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from sentio.api.app import PREFIX, agent, app
from sentio.config import emotion_cfg
from sentio.session.models import EmotionEvent
from tests.helpers import login_student

TELEMETRY = {
    "attention_score": 0.05,
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
    response = client.post(
        PREFIX + f"/student/{owner}/consent",
        json={"consent_version": "camera-v1", "preferences": {"telemetry": True}},
    )
    assert response.status_code == 200
    return owner, session_id


def _exported(client, owner):
    response = client.get(PREFIX + f"/student/{owner}/export")
    assert response.status_code == 200, response.text
    return response.json()["data"]["emotion_timeline"]


def test_export_includes_the_camera_history_and_telemetry_delete_removes_it():
    with patch.object(emotion_cfg, "ENABLED", True), TestClient(app) as client:
        owner, session_id = _session(client)
        before = time.time()
        assert (
            client.post(PREFIX + f"/sessions/{session_id}/telemetry", json=TELEMETRY).status_code
            == 200
        )
        agent.sm.get_or_raise(session_id).emotion_timeline.record(
            EmotionEvent(before - 5, "sad", "struggling", 0.8, "simplify")
        )

        history = _exported(client, owner)
        assert [(e["emotion"], e["learning_state"], e["confidence"]) for e in history] == [
            ("sad", "struggling", 0.8),
            ("looking_away", "disengaged", 0.95),
        ]
        assert all(
            set(e) == {"session_id", "timestamp", "emotion", "learning_state", "confidence"}
            for e in history
        )
        assert {e["session_id"] for e in history} == {session_id}

        # Closing the session writes its log file; the export must not list readings twice.
        assert client.delete(PREFIX + f"/sessions/{session_id}").status_code == 200
        assert len(_exported(client, owner)) == 2

        assert client.delete(PREFIX + f"/student/{owner}/telemetry").status_code == 200
        assert _exported(client, owner) == []


def test_export_only_has_the_students_own_camera_history():
    with patch.object(emotion_cfg, "ENABLED", True), TestClient(app) as client:
        _, session_id = _session(client)
        client.post(PREFIX + f"/sessions/{session_id}/telemetry", json=TELEMETRY)
        client.headers.pop("Authorization")
        other = login_student(client)
        assert _exported(client, other) == []


def test_withdrawing_consent_clears_the_live_readings_of_active_sessions():
    with patch.object(emotion_cfg, "ENABLED", True), TestClient(app) as client:
        owner, session_id = _session(client)
        client.post(PREFIX + f"/sessions/{session_id}/telemetry", json=TELEMETRY)
        timeline = lambda: agent.sm.get_or_raise(session_id).emotion_timeline  # noqa: E731
        assert len(timeline()) == 1
        again = client.post(
            PREFIX + f"/student/{owner}/consent",
            json={"consent_version": "camera-v1", "preferences": {"telemetry": True}},
        )
        assert again.status_code == 200
        assert len(timeline()) == 1  # Consent kept: readings stay.
        withdrawn = client.post(
            PREFIX + f"/student/{owner}/consent",
            json={"consent_version": "camera-v1", "preferences": {"telemetry": False}},
        )
        assert withdrawn.status_code == 200
        assert len(timeline()) == 0


def test_live_frames_are_analysed_at_most_once_a_second_per_connection():
    calls = []

    def detect(frame, session_id=None):
        calls.append(session_id)

    with (
        patch.object(emotion_cfg, "ENABLED", True),
        patch("sentio.emotion.routes.decode_frame", return_value=object()),
        patch.object(agent.detector, "detect_from_frame", side_effect=detect),
        TestClient(app) as client,
    ):
        _, session_id = _session(client)
        with client.websocket_connect(PREFIX + f"/ws/{session_id}") as ws:
            ws.send_json({"frame_b64": "x"})
            assert ws.receive_json()["face_detected"] is False
            for _ in range(3):
                ws.send_json({"frame_b64": "x"})
                assert ws.receive_json() == {"error": "Too many frames"}
            assert len(calls) == 1

            with patch("sentio.emotion.routes.FRAME_INTERVAL_SEC", 0.05):
                time.sleep(0.1)
                ws.send_json({"frame_b64": "x"})
                reply = ws.receive_json()
                assert reply.get("face_detected") is False, reply
            assert len(calls) == 2
