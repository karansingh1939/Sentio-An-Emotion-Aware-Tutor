"""The emotion side feature is off by default and accepts camera data only with consent."""

import base64
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from sentio.api.app import PREFIX, app
from sentio.config import emotion_cfg
from sentio.emotion.access import decode_frame
from tests.helpers import login_student

TELEMETRY = {
    "attention_score": 0.8,
    "focused": 1,
    "eye_openness": 0.7,
    "head_pose_pitch": 1.0,
    "head_pose_yaw": 2.0,
    "emotion": "focused",
}


def _frame(width, height):
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (width, height)).save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode()


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


def test_feature_is_off_by_default_and_hidden_from_clients():
    assert emotion_cfg.ENABLED is False
    with TestClient(app) as client:
        owner, session_id = _session(client)
        _consent(client, owner, True)
        assert client.get(PREFIX + "/ready").json()["camera"]["enabled"] is False
        telemetry = client.post(PREFIX + f"/sessions/{session_id}/telemetry", json=TELEMETRY)
        assert telemetry.status_code == 404
        chat = client.post(
            PREFIX + f"/sessions/{session_id}/chat",
            json={"message": "Hello", "frame_b64": _frame(64, 64)},
        )
        assert chat.status_code == 404
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(PREFIX + f"/ws/{session_id}") as ws:
                ws.send_json({"access_token": client.headers["Authorization"][7:]})
                ws.receive_json()


def test_enabled_feature_still_requires_current_consent():
    with patch.object(emotion_cfg, "ENABLED", True), TestClient(app) as client:
        owner, session_id = _session(client)
        path = PREFIX + f"/sessions/{session_id}/telemetry"
        assert client.post(path, json=TELEMETRY).status_code == 403
        _consent(client, owner, True)
        assert client.post(path, json=TELEMETRY).status_code == 200
        _consent(client, owner, False)
        assert client.post(path, json=TELEMETRY).status_code == 403


def test_oversized_or_invalid_frames_are_rejected_before_decoding():
    assert decode_frame(_frame(64, 64)) is not None
    assert decode_frame(_frame(1920, 1080)) is None
    assert decode_frame("not base64!") is None
    assert decode_frame("A" * (emotion_cfg.MAX_FRAME_BYTES * 2)) is None
    with patch.object(emotion_cfg, "ENABLED", True), TestClient(app) as client:
        owner, session_id = _session(client)
        _consent(client, owner, True)
        response = client.post(
            PREFIX + f"/sessions/{session_id}/chat",
            json={"message": "Hello", "frame_b64": _frame(1920, 1080)},
        )
        assert response.status_code == 422
