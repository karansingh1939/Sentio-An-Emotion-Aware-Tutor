from fastapi.testclient import TestClient

from sentio.api.app import agent, app
from tests.helpers import login_student


def test_saved_review_receipt_is_owner_scoped_and_does_not_reschedule():
    with TestClient(app) as client:
        owner = login_student(client)
        deck = client.post(
            "/api/v1/flashcards/decks", json={"student_id": owner, "deck_name": "Physics"}
        ).json()["deck_id"]
        agent.sm.save_flashcards(
            [{"front": "What is inertia?", "back": "Resistance to change."}], owner, "motion", deck
        )
        card = client.get(f"/api/v1/flashcards/reviews/due?student_id={owner}").json()["cards"][0]
        path = f"/api/v1/flashcards/{card['card_id']}"
        rating = client.post(
            path + "/review", json={"quality_score": 4, "request_id": "lost-rating-response"}
        ).json()
        receipt = client.get(path + "/reviews/lost-rating-response")
        assert receipt.status_code == 200
        assert receipt.json()["quality_score"] == 4
        assert receipt.json()["result"] == rating
        assert agent.sm.get_flashcard(card["card_id"])["repetition_count"] == 1
        login_student(client)
        assert client.get(path + "/reviews/lost-rating-response").status_code == 404
