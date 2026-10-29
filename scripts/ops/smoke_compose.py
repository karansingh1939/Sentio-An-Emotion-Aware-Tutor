"""Verify real Compose storage/restart behavior in a disposable home, without model downloads."""

import argparse
import json
import os
import secrets
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def run(output):
    root = Path(__file__).resolve().parents[2]
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Choose a new report path")
    report = {
        "status": "running",
        "checks": [],
        "scope": "Real Compose containers; missing model; storage/auth/recovery, not AI quality.",
    }
    token = None

    def call(method, path, body=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(
            "http://127.0.0.1:8000/api/v1" + path,
            data=None if body is None else json.dumps(body).encode(),
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    with tempfile.TemporaryDirectory(prefix="sentio-compose-") as directory:
        home = Path(directory)
        (home / "data").mkdir()
        (home / "models").mkdir()
        override = home / "compose-smoke.json"
        override.write_text(
            json.dumps(
                {
                    "services": {
                        "sentio-api": {
                            "image": "sentio:ci",
                            "user": f"{os.getuid()}:{os.getgid()}"
                            if hasattr(os, "getuid")
                            else "1000:1000",
                            "volumes": [
                                f"{home.as_posix()}/data:/app/data",
                                f"{home.as_posix()}/models:/app/models",
                            ],
                            "environment": {
                                "HF_HUB_OFFLINE": "1",
                                "TRANSFORMERS_OFFLINE": "1",
                                "OLLAMA_MODEL": "sentio-ci-missing-model",
                                "SENTIO_HOME": "/app/data/runtime",
                                "DATABASE_URL": "sqlite:////app/data/runtime/data/tutor_sessions.db",
                                "HOME": "/app/data",
                            },
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        env = dict(os.environ, API_SECRET=secrets.token_hex(32))
        command = [
            "docker",
            "compose",
            "--project-name",
            "sentio-smoke-" + uuid.uuid4().hex[:10],
            "-f",
            str(root / "docker-compose.yml"),
            "-f",
            str(override),
        ]

        def compose(*args):
            subprocess.run(command + list(args), cwd=root, env=env, check=True, timeout=300)

        def ready():
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                try:
                    result = call("GET", "/ready")
                    if result["storage"]["ready"]:
                        return result
                except (OSError, urllib.error.URLError):
                    pass
                time.sleep(1)
            raise TimeoutError("Compose API did not become ready")

        try:
            compose("up", "--no-build", "-d", "--wait", "--wait-timeout", "180")
            state = ready()
            assert state["ai"]["ready"] is False
            report["checks"].append("storage ready while configured AI model is missing")
            credentials = {
                "email": "smoke-" + uuid.uuid4().hex + "@example.com",
                "password": secrets.token_hex(16) + "Aa1!",
            }
            call("POST", "/auth/register", credentials)
            login = call("POST", "/auth/login", credentials)
            token = login["access_token"]
            owner = login["student_id"]
            session = call(
                "POST", "/sessions", {"student_id": owner, "subject": "physics", "topic": "inertia"}
            )
            call("PUT", "/study/preferences", {"daily_minutes": 45})
            report["checks"].append(
                "registration, authentication, session and preference persistence"
            )
            compose("restart", "sentio-api")
            ready()
            assert call("GET", "/study/preferences")["daily_minutes"] == 45
            assert (
                call("GET", "/sessions/" + session["session_id"])["session_id"]
                == session["session_id"]
            )
            report["checks"].append("saved work and the same bearer token survive API restart")
            compose("stop", "ollama")
            assert ready()["ai"]["ready"] is False
            assert call("GET", "/study/preferences")["daily_minutes"] == 45
            report["checks"].append("saved browsing remains available after the provider stops")
            report["status"] = "passed"
        except Exception as exc:
            report.update(status="failed", failure=type(exc).__name__)
            subprocess.run(
                command + ["logs", "--no-color", "--tail", "100", "sentio-api"],
                cwd=root,
                env=env,
                check=False,
                timeout=30,
            )
            raise
        finally:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            # This random Compose project and its volumes were created only for this test.
            compose("down", "--volumes")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output)
