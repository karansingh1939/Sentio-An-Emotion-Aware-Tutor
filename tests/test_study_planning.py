from datetime import date

from fastapi.testclient import TestClient

from sentio.api.app import agent, app


def account(client, email):
    credentials = {"email": email, "password": "StrongPassword123!"}
    assert client.post("/api/v1/auth/register", json=credentials).status_code == 201
    result = client.post("/api/v1/auth/login", json=credentials).json()
    return {"Authorization": "Bearer " + result["access_token"]}, result["student_id"]


def test_daily_queue_is_bounded_stable_owned_and_survives_restart():
    from sentio.study.planning import PlanningService

    with TestClient(app) as client:
        headers, owner = account(client, "daily-plan@example.com")
        other, _ = account(client, "other-plan@example.com")
        prefix = "/api/v1/study"
        assert (
            client.put(
                prefix + "/preferences", headers=headers, json={"daily_minutes": 20}
            ).status_code
            == 200
        )
        goal = client.post(
            f"/api/v1/students/{owner}/goals",
            headers=headers,
            json={"goal_text": "Prepare for mechanics exam", "topic_id": "mechanics"},
        ).json()["goal_id"]
        first = client.get(prefix + "/daily-plan?day=2026-10-12", headers=headers).json()
        assert first["tasks"] and sum(task["minutes"] for task in first["tasks"]) <= 20
        assert first == client.get(prefix + "/daily-plan?day=2026-10-12", headers=headers).json()
        task = first["tasks"][0]
        assert (
            client.patch(
                prefix + f"/daily-plan/2026-10-12/tasks/{task['task_id']}",
                headers=other,
                json={"completed": True},
            ).status_code
            == 404
        )
        assert (
            client.patch(
                prefix + f"/daily-plan/2026-10-12/tasks/{task['task_id']}",
                headers=headers,
                json={"completed": True},
            ).status_code
            == 200
        )
        restored = PlanningService(agent.sm.persister._engine).daily_plan(owner, date(2026, 10, 12))
        assert restored["tasks"][0]["completed_at"] is not None
        assert restored["tasks"][0]["completion_evidence"] == "self_reported"
        assert (
            client.patch(
                f"/api/v1/students/{owner}/goals/{goal}",
                headers=other,
                json={"status": "completed"},
            ).status_code
            == 403
        )
        updated = client.patch(
            f"/api/v1/students/{owner}/goals/{goal}", headers=headers, json={"status": "completed"}
        ).json()
        assert updated["goal"]["completed_at"] is not None
        assert (
            client.put(
                prefix + "/preferences", headers=headers, json={"daily_minutes": 0}
            ).status_code
            == 422
        )
        assert client.get(prefix + "/daily-plan?day=not-a-date", headers=headers).status_code == 422


def test_planning_prioritizes_due_reviews_and_feedback_reports_sample_size():
    from sqlalchemy import text

    from sentio.study.planning import PlanningService

    with TestClient(app) as client:
        headers, owner = account(client, "review-plan@example.com")
        with agent.sm.persister._engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO flashcards (card_id,student_id,topic_id,front_text,back_text,created_at,next_review_at) VALUES ('planning-card',:owner,'mechanics','Force?','Mass times acceleration',1,1)"
                ),
                {"owner": owner},
            )
        service = PlanningService(agent.sm.persister._engine)
        plan = service.daily_plan(owner, date(2026, 10, 13))
        assert plan["tasks"][0]["kind"] == "review"
        assert plan["tasks"][0]["evidence_count"] == 1
        feedback = service.feedback(owner)
        assert feedback["attempts"] == 0
        assert feedback["accuracy"] is None
        assert "Not assessed" in feedback["summary"]


def test_history_pagination_is_owner_scoped():
    with TestClient(app) as client:
        headers, owner = account(client, "paged-history@example.com")
        for topic in ("Inertia", "Momentum", "Energy"):
            assert (
                client.post(
                    "/api/v1/sessions",
                    headers=headers,
                    json={
                        "student_id": owner,
                        "subject": "physics",
                        "topic": topic,
                        "difficulty": "beginner",
                    },
                ).status_code
                == 201
            )
        first = client.get("/api/v1/sessions?limit=2", headers=headers).json()
        assert first["total"] == 3 and first["next_offset"] == 2
        second = client.get("/api/v1/sessions?limit=2&offset=2", headers=headers).json()
        assert len(second["sessions"]) == 1 and second["next_offset"] is None
        assert not {s["session_id"] for s in first["sessions"]}.intersection(
            s["session_id"] for s in second["sessions"]
        )
