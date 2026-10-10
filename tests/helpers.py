"""Deterministic provider responses and real authentication for integration tests."""

import json
import uuid


def login_student(client, *, admin=False):
    from sentio.api.app import PREFIX, agent

    body = {"email": f"test-{uuid.uuid4().hex}@example.com", "password": "StrongPassword123!"}
    response = client.post(PREFIX + "/auth/register", json=body)
    assert response.status_code == 201, response.text
    student_id = response.json()["student_id"]
    if admin:
        account = agent.sm.persister.auth_repo.get_account_by_student_id(student_id)
        account.role = "admin"
        agent.sm.persister.auth_repo.save_account(account)
    response = client.post(PREFIX + "/auth/login", json=body)
    assert response.status_code == 200, response.text
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    return student_id


def complete(system_prompt, history, user_message, **kwargs):
    prompt = system_prompt.lower()
    if "generate a quiz" in prompt:
        questions = [
            dict(
                question_text="Which quantity measures disorder?",
                question_type="multiple_choice",
                options=["Entropy", "Energy", "Temperature", "Pressure"],
                correct_answer="Entropy",
            ),
            dict(
                question_text="Energy is conserved.",
                question_type="true_false",
                options=["True", "False"],
                correct_answer="True",
            ),
            dict(
                question_text="What does a thermometer measure?",
                question_type="short_answer",
                options=None,
                correct_answer="temperature",
            ),
        ]
        for question in questions:
            question.update(
                explanation="A thermodynamics concept.",
                difficulty="intermediate",
                topic="thermodynamics",
            )
        return json.dumps({"title": "Thermodynamics", "questions": questions}), 100
    if "flashcards about" in prompt:
        cards = [
            dict(front=term, back="A thermodynamics concept.", tags=["thermodynamics"])
            for term in ["Entropy", "Energy", "Temperature"]
        ]
        return json.dumps({"deck_name": "Thermodynamics", "cards": cards}), 50
    if "grade" in prompt:
        return json.dumps({"is_correct": False, "score": 0.0}), 10
    if "summary of student performance" in prompt:
        return "Keep practicing the concepts you missed.", 10
    return json.dumps(
        {
            "text": "Let's explore this concept.",
            "follow_up_question": "What do you think?",
            "encouragement": "Keep going!",
            "suggested_topic": "thermodynamics",
        }
    ), 30
