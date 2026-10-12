import importlib.util
import io
import json
from pathlib import Path
from unittest.mock import Mock

import yaml


def test_compose_production_defaults_pass_security_validation(monkeypatch):
    from sentio.config import APIConfig, validate_security_config

    root = Path(__file__).resolve().parents[1]
    environment = yaml.safe_load((root / "docker-compose.yml").read_text())["services"][
        "sentio-api"
    ]["environment"]
    monkeypatch.setenv("ENV", environment["ENV"])
    monkeypatch.setenv("API_SECRET", "compose-regression-only-secret-2026")
    monkeypatch.setenv("CORS_ORIGINS", environment.get("CORS_ORIGINS", "*"))
    validate_security_config(APIConfig())


def test_compose_smoke_is_disposable_and_reuses_auth_after_restart(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "scripts/smoke_compose.py"
    spec = importlib.util.spec_from_file_location("smoke_compose", path)
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    commands = []
    requests = []

    def compose(command, **kwargs):
        commands.append((command, kwargs))
        override = json.loads(
            Path(command[command.index("-f", command.index("-f") + 1) + 1]).read_text()
        )
        service = override["services"]["sentio-api"]
        assert "sentio-compose-" in service["volumes"][0]
        assert service["environment"]["HF_HUB_OFFLINE"] == "1"
        assert kwargs["env"]["API_SECRET"]
        return Mock(returncode=0)

    def urlopen(request, **kwargs):
        requests.append(request)
        path = request.full_url.split("/api/v1")[1]
        payload = {
            "/ready": {"storage": {"ready": True}, "ai": {"ready": False}},
            "/auth/register": {},
            "/auth/login": {"access_token": "test-token", "student_id": "test-owner"},
            "/sessions": {"session_id": "test-session"},
            "/sessions/test-session": {"session_id": "test-session"},
            "/study/preferences": {"daily_minutes": 45},
        }[path]
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(smoke.subprocess, "run", compose)
    monkeypatch.setattr(smoke.urllib.request, "urlopen", urlopen)
    result = smoke.run(tmp_path / "report.json")
    assert result["status"] == "passed"
    assert commands[-1][0][-2:] == ["down", "--volumes"]
    assert all(command[0][3].startswith("sentio-smoke-") for command in commands)
    assert len({command[1]["env"]["API_SECRET"] for command in commands}) == 1
    assert requests[-1].get_header("Authorization") == "Bearer test-token"
