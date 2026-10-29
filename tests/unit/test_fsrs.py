"""FSRS memory model: first intervals, growth, lapses, difficulty and SM-2 conversion."""

import pytest

from sentio.flashcards import fsrs

NOW = 1_800_000_000.0
NEW = {"interval_days": 0, "repetition_count": 0, "ease_factor": 2.5, "next_review_at": NOW}


def reviewed(stability, difficulty, days_ago):
    return {
        "stability": stability,
        "difficulty": difficulty,
        "last_review_at": NOW - days_ago * fsrs.DAY,
    }


def test_quality_scores_map_to_the_four_ratings():
    assert [fsrs.rating_from_quality(q) for q in range(6)] == [1, 1, 1, 2, 3, 4]


def test_recall_is_ninety_percent_after_one_stability_period():
    assert fsrs.retrievability(0, 5) == 1
    assert fsrs.retrievability(5, 5) == pytest.approx(0.9)
    assert fsrs.interval_days(5) == 5


def test_new_card_intervals_follow_the_default_parameters():
    assert fsrs.next_intervals(NEW, NOW) == {"again": 1, "hard": 1, "good": 3, "easy": 16}
    assert fsrs.recall_probability(NEW, NOW) is None


def test_recalling_on_time_grows_stability_and_easy_grows_it_most():
    card = reviewed(10, 5, days_ago=10)
    hard, good, easy = (fsrs.review(card, rating, NOW)[0] for rating in (2, 3, 4))
    assert 10 < hard < good < easy


def test_a_lapse_shrinks_stability_and_raises_difficulty():
    card = reviewed(30, 5, days_ago=30)
    stability, difficulty = fsrs.review(card, fsrs.AGAIN, NOW)
    assert stability < 30 and difficulty > 5


def test_difficulty_stays_between_one_and_ten():
    card = reviewed(5, 9.9, days_ago=5)
    for _ in range(20):
        stability, difficulty = fsrs.review(card, fsrs.AGAIN, NOW)
        card = reviewed(stability, difficulty, days_ago=5)
    assert difficulty <= 10
    for _ in range(20):
        stability, difficulty = fsrs.review(card, fsrs.EASY, NOW)
        card = reviewed(stability, difficulty, days_ago=5)
    assert difficulty >= 1


def test_cards_scheduled_by_sm2_are_converted_on_their_next_review():
    card = {"interval_days": 6, "repetition_count": 2, "ease_factor": 2.5, "next_review_at": NOW}
    stability, difficulty, last_review_at = fsrs.memory_state(card)
    assert (stability, difficulty, last_review_at) == (6.0, 6.0, NOW - 6 * fsrs.DAY)
    assert fsrs.recall_probability(card, NOW) == pytest.approx(0.9)
    assert fsrs.review(card, fsrs.GOOD, NOW)[0] > 6
