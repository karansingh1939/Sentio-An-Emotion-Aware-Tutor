"""Difficulty follows the learner: explicit requests and quiz streaks only, visible and undoable."""

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from sentio.ai.providers import OllamaBackend
from sentio.api.app import agent, app
from tests.helpers import complete, login_student, upload_notes

NOTES = (
    "Diamond is harder than graphite because each carbon atom bonds to four others. "
    "Graphite has layers that slide, so it is soft."
)
QUESTION = {
    "question_text": "Why is diamond hard?",
    "question_type": "multiple_choice",
    "options": ["Four bonds per carbon atom", "Sliding layers", "It is a metal", "Water"],
    "correct_answer": "Four bonds per carbon atom",
    "explanation": "Each carbon atom bonds to four others.",
    "difficulty": "intermediate",
    "topic": "x",
}


def provider(self, system_prompt, history, user_message, **kwargs):
    if "generate a quiz" in system_prompt.lower():
        return json.dumps({"title": "Carbon", "questions": [QUESTION] * 3}), 30
    return complete(system_prompt, history, user_message, **kwargs)


def _session(client, difficulty="intermediate"):
    owner = login_student(client)
    notes = upload_notes(client, NOTES, "carbon.txt")
    session = client.post(
        "/api/v1/sessions",
        json={
            "student_id": owner,
            "topic": "Carbon",
            "difficulty": difficulty,
            "metadata": {"document_id": notes},
        },
    ).json()["session_id"]
    return owner, session


def _ask(client, session, message, request_id):
    stream = client.post(
        f"/api/v1/sessions/{session}/chat/stream",
        json={"message": message, "request_id": request_id},
    ).text
    return json.loads(stream.split("event: complete\ndata: ")[1].split("\n")[0])


def _quiz(client, owner, session, answer):
    quiz = client.post(
        "/api/v1/quizzes/generate",
        json={"student_id": owner, "session_id": session, "topic": "Carbon", "num_questions": 3},
    ).json()
    return client.post(
        f"/api/v1/quizzes/{quiz['quiz_id']}/submit",
        json={"session_id": session, "answers": {i: answer for i in range(3)}},
    ).json()


def test_content_questions_keep_the_chosen_level_and_requests_change_it(monkeypatch):
    monkeypatch.setattr(OllamaBackend, "complete", provider)
    with TestClient(app) as client:
        _, session = _session(client)
        first = _ask(client, session, "Why is diamond harder than graphite?", "diamond-question")
        assert first["difficulty"] == "intermediate" and "difficulty_change" not in first
        assert agent.sm.get_or_raise(session).difficulty == "intermediate"

        harder = _ask(client, session, "Can you make it harder?", "request-harder-1")
        assert harder["difficulty_change"] == {
            "from": "intermediate",
            "to": "advanced",
            "reason": "request_harder",
            "reason_text": "you asked for harder",
        }
        assert agent.sm.get_or_raise(session).difficulty == "advanced"

        confused = _ask(client, session, "I'm lost, explain it another way", "confused-turn-1")
        assert confused["difficulty"] == "advanced" and "difficulty_change" not in confused


def test_quiz_streaks_step_once_and_undo_pins_the_level(monkeypatch):
    monkeypatch.setattr(OllamaBackend, "complete", provider)
    with TestClient(app) as client:
        owner, session = _session(client)
        result = _quiz(client, owner, session, "Water")
        assert result["difficulty_change"]["to"] == "beginner"
        assert result["difficulty_change"]["reason_text"] == "2 wrong answers in a row"

        undo = client.post(
            f"/api/v1/sessions/{session}/difficulty", json={"difficulty": "intermediate"}
        )
        assert undo.json() == {"difficulty": "intermediate", "pinned": True}
        again = _quiz(client, owner, session, "Water")
        assert "difficulty_change" not in again
        assert agent.sm.get_or_raise(session).difficulty == "intermediate"

        simpler = _ask(client, session, "Could you make it simpler?", "request-simpler-1")
        assert simpler["difficulty_change"]["to"] == "beginner"
        assert agent.sm.get_or_raise(session).metadata["difficulty_pinned"] is False

        assert (
            client.post(
                f"/api/v1/sessions/{session}/difficulty", json={"difficulty": "expert"}
            ).status_code
            == 422
        )
        login_student(client)
        assert client.post(
            f"/api/v1/sessions/{session}/difficulty", json={"difficulty": "beginner"}
        ).status_code in (403, 404)


def test_three_correct_answers_step_up_by_one_level(monkeypatch):
    monkeypatch.setattr(OllamaBackend, "complete", provider)
    with TestClient(app) as client:
        owner, session = _session(client, "beginner")
        result = _quiz(client, owner, session, QUESTION["correct_answer"])
        assert result["difficulty_change"]["to"] == "intermediate"
        assert agent.sm.get_or_raise(session).difficulty == "intermediate"


def test_emotion_never_changes_difficulty():
    with TestClient(app) as client:
        _, session = _session(client)
        reading = SimpleNamespace(emotion="sad", learning_state="struggling", confidence=0.9)
        for _ in range(10):
            agent.sm.record_emotion(session, reading)
        assert agent.sm.get_or_raise(session).difficulty == "intermediate"
