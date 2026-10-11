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
        assert rejected.status_code == 429 and rejected.headers["Retry-After"] == "1"
        for _ in range(3):
            assert client.post("/resource").status_code == 200
        assert client.post("/resource").status_code == 429
