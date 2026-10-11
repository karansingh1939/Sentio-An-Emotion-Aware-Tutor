from fastapi.testclient import TestClient
from sqlalchemy import text

from sentio.api.app import agent, app
from tests.test_study_planning import account


def test_saved_practice_and_edits_are_owned_and_rating_retry_is_atomic(monkeypatch):
    with TestClient(app) as client:
        headers, owner = account(client, "saved-practice@example.com")
        other, _ = account(client, "saved-practice-other@example.com")
        session = client.post(
            "/api/v1/sessions",
            headers=headers,
            json={
                "student_id": owner,
                "subject": "physics",
                "topic": "Inertia",
                "difficulty": "beginner",
            },
        ).json()["session_id"]
        agent.sm.save_quiz(
            "saved-quiz",
            owner,
            session,
            "Saved mechanics",
            [
                {
                    "question_text": "Force?",
                    "question_type": "mcq",
                    "options": ["ma", "m/a"],
                    "correct_answer": "ma",
                    "explanation": "Newton's second law",
                    "difficulty": "beginner",
                    "topic": "Inertia",
                }
            ],
        )
        with agent.sm.persister._engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO flashcards (card_id,student_id,topic_id,front_text,back_text,created_at,next_review_at) VALUES ('editable-card',:owner,'Inertia','Old term','Old answer',1,1)"
                ),
                {"owner": owner},
            )
        assert (
            client.get("/api/v1/quizzes?limit=1", headers=headers).json()["quizzes"][0]["quiz_id"]
            == "saved-quiz"
        )
        assert client.get("/api/v1/quizzes/saved-quiz", headers=other).status_code == 404
        assert (
            client.get("/api/v1/quizzes/saved-quiz", headers=headers).json()["questions"][0][
                "explanation"
            ]
            == "Newton's second law"
        )
        assert (
            client.patch(
                "/api/v1/flashcards/editable-card",
                headers=other,
                json={"front_text": "Force?", "back_text": "Mass times acceleration"},
            ).status_code
            == 404
        )
        edit = client.patch(
            "/api/v1/flashcards/editable-card",
            headers=headers,
            json={"front_text": "Force?", "back_text": "Mass times acceleration"},
        )
        assert edit.status_code == 200
        assert agent.sm.get_flashcard("editable-card")["back_text"] == "Mass times acceleration"
        body = {"quality_score": 4, "request_id": "review-one"}
        first = client.post("/api/v1/flashcards/editable-card/review", headers=headers, json=body)
        repeated = client.post(
            "/api/v1/flashcards/editable-card/review", headers=headers, json=body
        )
        assert first.status_code == 200 and repeated.json() == first.json()
        assert agent.sm.get_flashcard("editable-card")["repetition_count"] == 1
        assert (
            client.post(
                "/api/v1/flashcards/editable-card/review",
                headers=headers,
                json={**body, "quality_score": 1},
            ).status_code
            == 409
        )
        monkeypatch.setattr(
            agent.sm,
            "update_flashcard_review",
            lambda **kwargs: (_ for _ in ()).throw(OSError("write failed")),
        )
        with agent.sm.persister._engine.connect() as connection:
            attempts = connection.execute(
                text(
                    "SELECT attempts_count FROM student_knowledge WHERE student_id=:owner AND topic_id='Inertia'"
                ),
                {"owner": owner},
            ).scalar()
        assert (
            client.post(
                "/api/v1/flashcards/editable-card/review",
                headers=headers,
                json={**body, "request_id": "review-two"},
            ).status_code
            == 503
        )
        with agent.sm.persister._engine.connect() as connection:
            assert (
                connection.execute(
                    text(
                        "SELECT attempts_count FROM student_knowledge WHERE student_id=:owner AND topic_id='Inertia'"
                    ),
                    {"owner": owner},
                ).scalar()
                == attempts
            )
        assert agent.sm.get_flashcard("editable-card")["repetition_count"] == 1
