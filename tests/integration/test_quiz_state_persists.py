"""Quiz answers graded on their own are saved, so History and a restart agree with them."""


def test_graded_answers_change_the_saved_level_not_only_the_live_one():
    from fastapi.testclient import TestClient

    from sentio.api.app import agent, app
    from tests.helpers import login_student

    with TestClient(app) as client:
        owner = login_student(client)
        uploaded = client.post(
            "/api/v1/documents/upload",
            files={"file": ("motion.txt", b"Inertia resists changes in motion.", "text/plain")},
        )
        sid = client.post(
            "/api/v1/sessions",
            json={
                "student_id": owner,
                "subject": "physics",
                "topic": "Any topic",
                "difficulty": "beginner",
                "metadata": {"document_id": uploaded.json()["document_id"]},
            },
        ).json()["session_id"]
        for _ in range(3):
            assert (
                client.post(f"/api/v1/sessions/{sid}/quiz", json={"correct": True}).status_code
                == 200
            )
        assert client.get(f"/api/v1/sessions/{sid}").json()["difficulty"] == "intermediate"

        # History reads the saved session (D12).
        listed = next(
            s
            for s in client.get("/api/v1/sessions?limit=50").json()["sessions"]
            if s["session_id"] == sid
        )
        assert listed["difficulty"] == "intermediate"

        # A restart rebuilds the session from what was saved (R2).
        agent.sm._sessions.pop(sid, None)
        reloaded = agent.sm.get_session(sid)
        assert reloaded.difficulty == "intermediate"
        assert reloaded.quiz_tracker.consecutive_correct == 0
