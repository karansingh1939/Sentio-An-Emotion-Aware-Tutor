"""Startup and installation contracts, without live model generation."""

from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient

from sentio.api.app import agent, app
from sentio.auth.middleware import get_current_user
from sentio.shared.exceptions import LLMServiceUnavailableError


def test_packaged_frontend_and_provider_failure(monkeypatch):
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/static/js/core/tutor_runtime.js").status_code == 200
    assert (
        len(
            [
                path
                for path in client.get("/openapi.json").json()["paths"]
                if path.startswith("/api/v1")
            ]
        )
        >= 40
    )
    session = SimpleNamespace(student_id="test", is_active=True)
    monkeypatch.setattr(agent.sm, "get_session", lambda sid: session)
    monkeypatch.setattr(
        agent, "chat", Mock(side_effect=LLMServiceUnavailableError("ollama", "offline"))
    )
    app.dependency_overrides[get_current_user] = lambda: {"student_id": "test", "role": "student"}
    try:
        response = client.post("/api/v1/sessions/test/chat", json={"message": "Explain gravity"})
        assert response.status_code == 503, response.text
    finally:
        app.dependency_overrides.pop(get_current_user)
        client.close()


def test_missing_model_disables_inference(tmp_path):
    from sentio.emotion.detector import EmotionDetector

    detector = EmotionDetector()
    detector.build_model = Mock()
    detector.load_model(tmp_path / "missing.h5")
    detector.build_model.assert_not_called()
    assert detector.model is None


def test_health_check_does_not_import_optional_ml_libraries(monkeypatch):
    import builtins

    from sentio.maintenance.health_check import system_health_check

    original_import = builtins.__import__
    optional = {
        "sentence_transformers",
        "sklearn",
        "pandas",
        "matplotlib",
        "transformers",
    }

    def guarded_import(name, *args, **kwargs):
        if name in optional:
            raise AssertionError(f"Health check imported optional library: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    report = system_health_check()
    assert "sentence-transformers" in report["optional_packages"]
