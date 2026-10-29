import json
import threading
import time
import uuid
from queue import Empty

import pytest
from fastapi.testclient import TestClient

from sentio.ai.streaming import visible_text
from sentio.api.app import agent, app
from sentio.jobs.control import current_control


@pytest.fixture
def study():
    with TestClient(app) as client:
        email = f"stream-{uuid.uuid4()}@example.com"
        credentials = {"email": email, "password": "StrongPassword123!"}
        assert client.post("/api/v1/auth/register", json=credentials).status_code == 201
        tokens = client.post("/api/v1/auth/login", json=credentials).json()
        headers = {"Authorization": "Bearer " + tokens["access_token"]}
        session = client.post(
            "/api/v1/sessions",
            headers=headers,
            json={
                "student_id": "ignored",
                "subject": "physics",
                "topic": "Newton's First Law",
                "difficulty": "beginner",
            },
        ).json()["session_id"]
        yield client, headers, session


def finish(events):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            kind, data = events.get(timeout=0.05)
        except Empty:
            continue
        if kind in ("complete", "error", "cancelled"):
            return kind, data
    pytest.fail("Turn did not finish")


def test_readable_json_stream_handles_fragmented_escapes_and_nested_fields():
    raw = json.dumps({"metadata": {"text": "never show"}, "text": 'line\n"quote" café 😀'})
    emitted = ""
    for end in range(len(raw) + 1):
        text = visible_text(raw[:end])
        assert text.startswith(emitted)
        emitted = text
    assert emitted == 'line\n"quote" café 😀'
    assert visible_text("raw JSON should not show") == ""


def test_completed_turn_replay_is_persisted_and_does_not_double_count(study):
    client, headers, sid = study
    body = {"message": "Explain Newton's First Law", "request_id": "unique-request"}
    first = client.post(f"/api/v1/sessions/{sid}/chat/stream", headers=headers, json=body)
    assert first.status_code == 200, first.text
    assert "event: complete" in first.text, first.text
    assert agent.sm.get_or_raise(sid).total_exchanges == 1
    repeated = client.post(f"/api/v1/sessions/{sid}/chat/stream", headers=headers, json=body)
    assert "event: complete" in repeated.text
    assert agent.sm.get_or_raise(sid).total_exchanges == 1
    body["message"] = "Different message"
    assert (
        client.post(f"/api/v1/sessions/{sid}/chat/stream", headers=headers, json=body).status_code
        == 409
    )
    persisted = agent.sm.persister.load_session_data(sid)
    assert persisted["total_exchanges"] == 1


def test_cancellation_and_source_change_never_record_completed_exchange(study, monkeypatch):
    _, _, sid = study
    session = agent.sm.get_or_raise(sid)
    started = threading.Event()
    release = threading.Event()

    def slow(**kwargs):
        assert current_control() is not None, "Cancellation scope must reach graph nodes"
        started.set()
        release.wait(4)
        return json.dumps({"text": "Valid but stopped answer"}), 10

    monkeypatch.setattr(agent.nlp._backend, "complete", slow)
    service = app.state.streams
    events, _ = service.begin(session.student_id, sid, "cancel-me", "Explain inertia")
    assert started.wait(3)
    assert service.cancel(session.student_id, sid, "cancel-me")
    release.set()
    assert finish(events)[0] == "cancelled"
    assert session.total_exchanges == 0
    assert agent.nlp._get_history(sid).to_list() == []


def test_source_switch_cancels_running_turn(study, monkeypatch):
    client, headers, sid = study
    session = agent.sm.get_or_raise(sid)
    started, release = threading.Event(), threading.Event()

    def slow(**kwargs):
        started.set()
        release.wait(4)
        return json.dumps({"text": "Previous source answer"}), 10

    monkeypatch.setattr(agent.nlp._backend, "complete", slow)
    events, _ = app.state.streams.begin(session.student_id, sid, "switch-source", "Explain inertia")
    assert started.wait(3)
    response = client.post(
        f"/api/v1/sessions/{sid}/grounding", headers=headers, json={"document_id": "all"}
    )
    assert response.status_code == 200
    release.set()
    assert finish(events)[0] == "cancelled"
    assert session.total_exchanges == 0
    assert session.metadata["document_id"] == "all"


def test_queued_turn_cancellation_sends_terminal_event(study):
    _, _, sid = study
    session = agent.sm.get_or_raise(sid)
    started, release = threading.Event(), threading.Event()

    def blocking(control):
        started.set()
        release.wait(4)
        control.check()

    app.state.jobs.submit(session.student_id, "blocker", blocking)
    assert started.wait(3)
    events, _ = app.state.streams.begin(session.student_id, sid, "queued-cancel", "Explain inertia")
    assert app.state.streams.cancel(session.student_id, sid, "queued-cancel")
    release.set()
    assert finish(events)[0] == "cancelled"
    assert sid not in app.state.streams.active
    assert session.total_exchanges == 0


def test_malformed_output_is_error_and_never_a_completed_turn(study, monkeypatch):
    client, headers, sid = study
    monkeypatch.setattr(agent.nlp._backend, "complete", lambda **kw: ('{"text":"unfinished', 10))
    response = client.post(
        f"/api/v1/sessions/{sid}/chat/stream",
        headers=headers,
        json={"message": "Explain inertia", "request_id": "malformed-output"},
    )
    assert "event: error" in response.text
    assert "event: complete" not in response.text
    assert agent.sm.get_or_raise(sid).total_exchanges == 0


@pytest.mark.parametrize("terminal", ["cancelled", "complete", "error"])
def test_full_stream_buffer_still_delivers_terminal_event(study, monkeypatch, terminal):
    _, _, sid = study
    session = agent.sm.get_or_raise(sid)
    release = threading.Event()
    original_chat = agent.chat

    def fill_buffer(*args, **kwargs):
        assert release.wait(3)
        response = original_chat(*args, **kwargs) if terminal == "complete" else None
        while not events.full():
            current_control().emit("delta", {"text": "partial "})
        if terminal == "cancelled":
            current_control().emit("delta", {"text": "overflow"})
        if terminal == "error":
            raise RuntimeError("Synthetic provider failure with a full buffer")
        return response

    monkeypatch.setattr(agent, "chat", fill_buffer)
    events, job_id = app.state.streams.begin(
        session.student_id, sid, "full-buffer-" + terminal, "Explain inertia"
    )
    release.set()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = app.state.jobs.get(job_id, session.student_id)
        if job["status"] in ("succeeded", "failed", "cancelled"):
            break
        time.sleep(0.01)
    else:
        pytest.fail("Worker did not finish with a full stream buffer")
    assert finish(events)[0] == terminal
    assert session.total_exchanges == (1 if terminal == "complete" else 0)
    assert len(app.state.streams.turns(session.student_id, sid)) == (
        1 if terminal == "complete" else 0
    )
    assert (
        job["status"]
        == {"complete": "succeeded", "error": "failed", "cancelled": "cancelled"}[terminal]
    )
