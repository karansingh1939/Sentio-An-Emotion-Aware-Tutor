"""A study session can be bound to one of its owner's active goals as versioned context."""

from fastapi.testclient import TestClient

from sentio.api.app import PREFIX, agent, app
from tests.helpers import login_student

SESSION = {"subject": "physics", "topic": "Mechanics", "difficulty": "beginner"}


def _goal(client, owner, text="Prepare for the mechanics exam"):
    response = client.post(PREFIX + f"/students/{owner}/goals", json={"goal_text": text})
    assert response.status_code == 201, response.text
    return response.json()["goal_id"]


def _session(client, owner, **metadata):
    body = {**SESSION, "student_id": owner, "metadata": {"document_id": "none", **metadata}}
    return client.post(PREFIX + "/sessions", json=body)


def test_owner_binds_changes_and_clears_a_session_goal():
    with TestClient(app) as client:
        owner = login_student(client)
        exam = _goal(client, owner)
        revision = _goal(client, owner, "Revise kinematics graphs")
        created = _session(client, owner, goal_id=exam)
        assert created.status_code == 201, created.text
        session_id = created.json()["session_id"]

        context = client.get(PREFIX + f"/sessions/{session_id}/context").json()
        assert context["goal"] == {"goal_id": exam, "goal_text": "Prepare for the mechanics exam"}

        changed = client.post(PREFIX + f"/sessions/{session_id}/goal", json={"goal_id": revision})
        assert changed.status_code == 200, changed.text
        assert changed.json()["goal"]["goal_text"] == "Revise kinematics graphs"
        assert client.get(PREFIX + f"/sessions/{session_id}").json()["metadata"]["goal_id"] == (
            revision
        )

        cleared = client.post(PREFIX + f"/sessions/{session_id}/goal", json={"goal_id": None})
        assert cleared.status_code == 200
        assert client.get(PREFIX + f"/sessions/{session_id}/context").json()["goal"] is None


def test_goals_of_other_students_or_completed_goals_cannot_be_bound():
    with TestClient(app) as client:
        other_owner = login_student(client)
        foreign = _goal(client, other_owner)
        owner = login_student(client)
        finished = _goal(client, owner, "Finished goal")
        assert (
            client.patch(
                PREFIX + f"/students/{owner}/goals/{finished}", json={"status": "completed"}
            ).status_code
            == 200
        )

        assert _session(client, owner, goal_id=foreign).status_code == 404
        session_id = _session(client, owner).json()["session_id"]
        for goal_id in (foreign, finished, "missing-goal"):
            response = client.post(
                PREFIX + f"/sessions/{session_id}/goal", json={"goal_id": goal_id}
            )
            assert response.status_code == 404, goal_id
        assert client.get(PREFIX + f"/sessions/{session_id}/context").json()["goal"] is None


def test_editing_or_completing_the_bound_goal_changes_the_study_context_version():
    with TestClient(app) as client:
        owner = login_student(client)
        goal = _goal(client, owner)
        session_id = _session(client, owner, goal_id=goal).json()["session_id"]
        session = agent.sm.get_session(session_id)
        streams = app.state.streams
        original_stream = streams.context(session)
        original_snapshot = client.get(PREFIX + f"/sessions/{session_id}/context").json()

        client.patch(
            PREFIX + f"/students/{owner}/goals/{goal}", json={"goal_text": "Prepare for finals"}
        )
        edited_snapshot = client.get(PREFIX + f"/sessions/{session_id}/context").json()
        assert edited_snapshot["goal"]["goal_text"] == "Prepare for finals"
        assert edited_snapshot != original_snapshot
        assert streams.context(session) != original_stream

        client.patch(PREFIX + f"/students/{owner}/goals/{goal}", json={"status": "completed"})
        assert client.get(PREFIX + f"/sessions/{session_id}/context").json()["goal"] is None


def test_tutor_receives_the_bound_goal_as_learner_context(monkeypatch):
    from sentio.ai.providers import OllamaBackend
    from tests.helpers import complete

    prompts = []

    def recording(self, system_prompt, history, user_message, **kwargs):
        prompts.append(system_prompt + "\n" + user_message)
        return complete(system_prompt, history, user_message, **kwargs)

    monkeypatch.setattr(OllamaBackend, "complete", recording)
    with TestClient(app) as client:
        owner = login_student(client)
        goal = _goal(client, owner, "Master projectile motion before Friday")
        _goal(client, owner, "Unrelated chemistry goal")
        session_id = _session(client, owner, goal_id=goal).json()["session_id"]
        response = client.post(
            PREFIX + f"/sessions/{session_id}/chat", json={"message": "Explain velocity"}
        )
        assert response.status_code == 200, response.text
    assert any(
        "Goal for this study session: Master projectile motion before Friday" in prompt
        for prompt in prompts
    )
