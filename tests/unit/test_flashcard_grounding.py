import json

from tests.integration.test_grounded_study_loop import FACT, OTHER, TOPIC
from tests.integration.test_grounded_study_loop import study as study_fixture

study = study_fixture


def test_flashcards_use_selected_document_and_student_session(study):
    s = study
    s.backend.complete.return_value = (
        json.dumps(
            {
                "deck_name": "Forces",
                "cards": [
                    {"front": "What changes motion?", "back": "An external net force.", "tags": []}
                ],
            }
        ),
        20,
    )
    deck = s.client.post(
        s.prefix + "/flashcards/decks",
        headers=s.headers,
        json={"student_id": s.a, "deck_name": "Forces"},
    ).json()["deck_id"]
    response = s.client.post(
        s.prefix + "/flashcards/generate",
        headers=s.headers,
        json={
            "student_id": s.a,
            "deck_id": deck,
            "topic_id": TOPIC,
            "session_id": s.session_id,
            "num_cards": 1,
        },
    )
    assert response.status_code == 200, response.text
    prompt = s.backend.complete.call_args.kwargs["system_prompt"]
    assert FACT in prompt
    assert OTHER not in prompt


def test_flashcards_reject_another_students_session(study):
    s = study
    deck = s.client.post(
        s.prefix + "/flashcards/decks",
        headers=s.headers_b,
        json={"student_id": s.b, "deck_name": "Forces"},
    ).json()["deck_id"]
    response = s.client.post(
        s.prefix + "/flashcards/generate",
        headers=s.headers_b,
        json={"student_id": s.b, "deck_id": deck, "topic_id": TOPIC, "session_id": s.session_id},
    )
    assert response.status_code == 403
