from fastapi import FastAPI
from fastapi.testclient import TestClient

from sentio.api.middleware import RateLimitMiddleware


def test_polling_cannot_exhaust_submission_budget_and_both_remain_limited():
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, rate=0.001, burst=3)

    @app.api_route("/resource", methods=["GET", "POST"])
    def resource():
        return {"ok": True}

    with TestClient(app) as client:
        for _ in range(3):
            assert client.get("/resource").status_code == 200
        rejected = client.get("/resource")
        assert rejected.status_code == 429 and int(rejected.headers["Retry-After"]) >= 1
        for _ in range(3):
            assert client.post("/resource").status_code == 200
        assert client.post("/resource").status_code == 429


def test_auth_has_its_own_stricter_budget_and_retry_after_is_usable(monkeypatch):
    from types import SimpleNamespace

    from sentio.shared import utils

    now = [0.0]
    monkeypatch.setattr(utils, "time", SimpleNamespace(perf_counter=lambda: now[0]))
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.post("/api/v1/auth/login")
    def login():
        return {"ok": True}

    @app.post("/api/v1/practice")
    def practice():
        return {"ok": True}

    with TestClient(app) as client:
        for _ in range(10):
            assert client.post("/api/v1/auth/login").status_code == 200
        rejected = client.post("/api/v1/auth/login")
        assert rejected.status_code == 429
        assert client.post("/api/v1/practice").status_code == 200
        now[0] += int(rejected.headers["Retry-After"])
        assert client.post("/api/v1/auth/login").status_code == 200
