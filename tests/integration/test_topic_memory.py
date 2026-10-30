"""Ready fades as a topic is forgotten, and flashcard reviews count toward topics."""

import json
import time

from fastapi.testclient import TestClient
from sqlalchemy import text

from sentio.ai.providers import OllamaBackend
from sentio.api.app import agent, app
from sentio.flashcards import fsrs
from tests.helpers import complete, login_student
from tests.integration.test_syllabus_progress import SYLLABUS
from tests.integration.test_topic_mastery import _quiz, _study

CARDS = [
    {"front": "What does a page table map?", "back": "Each page to a frame.", "tags": []},
    {"front": "What does paging split memory into?", "back": "Fixed size frames.", "tags": []},
]


def _age(days):
    """Move every answer and card review the given number of days into the past."""
    with agent.sm.persister._engine.begin() as connection:
        for update in (
            "UPDATE quiz_attempts SET timestamp=timestamp-:gap",
            "UPDATE card_reviews SET created_at=created_at-:gap",
        ):
            connection.execute(text(update), {"gap": days * fsrs.DAY})


def _topic(client, document, title):
    topics = client.get(f"/api/v1/documents/{document}/topics").json()["topics"]
    return next(topic for topic in topics if topic["title"] == title)


def test_ready_fades_and_a_correct_answer_brings_it_back_for_longer(monkeypatch):
    with TestClient(app) as client:
        owner, course, document, session = _study(client)
        assert _topic(client, document, "Paging")["recall"] is None

        _quiz(client, monkeypatch, owner, session, "paging", "Frames")
        topic = _topic(client, document, "Paging")
        assert topic["state"] == "ready" and topic["recall"] == 1
        first_gap = topic["review_on"] - time.time()
        assert 3 * fsrs.DAY < first_gap < 3.3 * fsrs.DAY
        assert client.get("/api/v1/topics/due").json() == {"topics": []}

        _age(4)
        topic = _topic(client, document, "Paging")
        assert topic["state"] == "review_due" and topic["recall"] < fsrs.DESIRED_RETENTION
        progress = client.get(f"/api/v1/courses/{course}/progress").json()
        assert (progress["summary"]["ready"], progress["summary"]["review_due"]) == (0, 1)
        assert [t["title"] for t in progress["due"]] == ["Paging"]
        assert progress["weak"] == []
        assert [t["title"] for t in client.get("/api/v1/topics/due").json()["topics"]] == ["Paging"]

        _quiz(client, monkeypatch, owner, session, "paging", "Frames")
        topic = _topic(client, document, "Paging")
        assert topic["state"] == "ready"
        assert topic["review_on"] - time.time() > 2 * first_gap

        _age(4)
        login_student(client)
        assert client.get("/api/v1/topics/due").json() == {"topics": []}


def test_a_wrong_answer_on_a_due_topic_makes_it_weak_again(monkeypatch):
    with TestClient(app) as client:
        owner, course, document, session = _study(client)
        _quiz(client, monkeypatch, owner, session, "paging", "Frames")
        _age(4)
        _quiz(client, monkeypatch, owner, session, "paging", "Threads")
        assert _topic(client, document, "Paging")["state"] == "practising"
        progress = client.get(f"/api/v1/courses/{course}/progress").json()
        assert [t["title"] for t in progress["weak"]] == ["Paging"]
        assert progress["due"] == []


def test_a_fading_topic_stops_counting_as_ready_on_the_syllabus(monkeypatch):
    with TestClient(app) as client:
        owner, course, _, session = _study(client)
        client.put(f"/api/v1/courses/{course}/syllabus", data={"text": SYLLABUS})
        _quiz(client, monkeypatch, owner, session, "paging", "Frames")
        assert client.get(f"/api/v1/courses/{course}/syllabus").json()["summary"][
            "percent_ready"
        ] == (25)

        _age(4)
        syllabus = client.get(f"/api/v1/courses/{course}/syllabus").json()
        assert syllabus["items"][0]["status"] == "review_due"
        assert syllabus["summary"]["review_due"] == 1
        assert syllabus["summary"]["percent_ready"] == 0


def test_flashcard_reviews_count_toward_the_topic_on_their_slide(monkeypatch):
    def provider(self, system_prompt, history, user_message, **kwargs):
        if "flashcards about" in system_prompt.lower():
            cards = [{**CARDS[0], "source": 2}, CARDS[1]]
            return json.dumps({"deck_name": "Paging", "cards": cards}), 30
        return complete(system_prompt, history, user_message, **kwargs)

    monkeypatch.setattr(OllamaBackend, "complete", provider)
    with TestClient(app) as client:
        owner, _, document, _ = _study(client)
        paging = _topic(client, document, "Paging")
        session = client.post(
            "/api/v1/sessions",
            json={
                "student_id": owner,
                "topic": "Paging",
                "metadata": {"document_id": document, "topic_ids": [paging["id"]]},
            },
        ).json()["session_id"]
        deck = client.post(
            "/api/v1/flashcards/decks", json={"student_id": owner, "deck_name": "Paging"}
        ).json()["deck_id"]
        made = client.post(
            "/api/v1/flashcards/generate",
            json={
                "student_id": owner,
                "deck_id": deck,
                "topic_id": "Paging",
                "num_cards": 2,
                "session_id": session,
            },
        )
        assert made.status_code == 200, made.text
        with agent.sm.persister._engine.connect() as connection:
            placed = connection.execute(
                text(
                    "SELECT source_document_id,source_page FROM flashcards WHERE deck_id=:deck ORDER BY source_page"
                ),
                {"deck": deck},
            ).fetchall()
        assert [tuple(row) for row in placed] == [(document, 1), (document, 2)]

        due = client.get(
            "/api/v1/flashcards/reviews/due", params={"student_id": owner, "deck_id": deck}
        ).json()
        for card in due["cards"]:
            review = client.post(
                f"/api/v1/flashcards/{card['card_id']}/review",
                json={"quality_score": 4, "student_id": owner},
            )
            assert review.status_code == 200, review.text
        topic = _topic(client, document, "Paging")
        assert (topic["state"], topic["answers"]) == ("practising", 2)
        assert topic["recall"] == 1


def test_older_reviews_without_a_slide_are_left_out(monkeypatch):
    with TestClient(app) as client:
        owner, _, document, session = _study(client)
        _quiz(client, monkeypatch, owner, session, "paging", "Frames")
        with agent.sm.persister._engine.begin() as connection:
            connection.execute(text("UPDATE quiz_questions SET source_document_id=NULL"))
        assert _topic(client, document, "Paging")["state"] == "not_started"
