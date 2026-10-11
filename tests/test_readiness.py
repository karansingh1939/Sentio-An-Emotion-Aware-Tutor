from unittest.mock import Mock

from fastapi.testclient import TestClient

from sentio.api.app import agent, app
from sentio.config import nlp_cfg
from sentio.tutor.tutor_agent import TutorAgent


def test_saved_material_ready_when_ollama_unavailable(monkeypatch):
    import requests

    agent.sm.load()
    monkeypatch.setattr(requests, "get", Mock(side_effect=requests.ConnectionError()))
    with TestClient(app) as client:
        response = client.get("/api/v1/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["storage"]["ready"] is True
        assert body["ai"]["ready"] is False
        assert "Ollama" in body["ai"]["action"]
        assert body["camera"]["experimental"] is True
        assert client.get("/").status_code == 200


def test_wrong_model_tag_does_not_report_ai_ready(monkeypatch):
    import requests

    monkeypatch.setattr(nlp_cfg, "OLLAMA_MODEL", "phi3:mini")
    reply = Mock()
    reply.json.return_value = {"models": [{"name": "phi3:medium"}]}
    monkeypatch.setattr(requests, "get", lambda *a, **kw: reply)
    body = TestClient(app).get("/api/v1/ready").json()
    assert body["ai"]["ready"] is False
    assert "phi3:mini" in body["ai"]["action"]


def test_startup_never_loads_camera_and_survives_ai_failure():
    detector, kb, nlp, sm = Mock(), Mock(), Mock(), Mock()
    nlp.load.side_effect = RuntimeError("provider offline")
    local = TutorAgent(detector=detector, kb=kb, nlp=nlp, sm=sm)
    local.load()
    detector.load_model.assert_not_called()
    assert local._loaded is True
    assert "ai" in local.startup_errors


def test_camera_model_loads_once_on_first_frame():
    import numpy as np

    detector = Mock(model=None)
    detector.detect_from_frame.return_value = None
    local = TutorAgent(detector=detector)
    local._detect_emotion(np.zeros((4, 4, 3)), session_id="test")
    local._detect_emotion(np.zeros((4, 4, 3)), session_id="test")
    assert detector.load_model.call_count == 1
