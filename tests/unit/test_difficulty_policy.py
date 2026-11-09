"""Difficulty changes only on explicit requests or quiz streaks, never on content words."""

import pytest

from sentio.tutor.difficulty import (
    asks_for_another_explanation,
    requested_change,
    step,
    streak_change,
)


@pytest.mark.parametrize(
    "message",
    [
        "Can you make it harder?",
        "make these questions more challenging",
        "This is too easy",
        "challenge me",
        "give me a harder example",
        "Harder questions please",
    ],
)
def test_requests_for_harder(message):
    assert requested_change(message) == "harder"


@pytest.mark.parametrize(
    "message",
    [
        "Could you make it simpler?",
        "this is way too complicated",
        "Explain that more simply please",
        "explain it in simple terms",
        "simplify this",
        "give me an easier example",
    ],
)
def test_requests_for_easier(message):
    assert requested_change(message) == "easier"


@pytest.mark.parametrize(
    "message",
    [
        "Why is diamond harder than graphite?",
        "How much energy is lost to friction?",
        "Which formula is simpler to use here?",
        "Is hard water harder to boil?",
        "What makes a problem NP-hard?",
        "Is this metal too hard to cut with steel?",
        "Explain the challenge of scheduling",
    ],
)
def test_questions_about_content_change_nothing(message):
    assert requested_change(message) is None
    assert not asks_for_another_explanation(message)


def test_confusion_asks_for_a_new_explanation_without_a_level_change():
    for message in ["I'm lost", "I don't understand recursion", "explain it another way"]:
        assert asks_for_another_explanation(message)
        assert requested_change(message) is None


def test_steps_stay_within_the_levels():
    assert step("beginner", "harder") == "intermediate"
    assert step("advanced", "harder") == "advanced"
    assert step("beginner", "easier") == "beginner"


def test_quiz_streaks():
    assert streak_change(3, 0) == ("harder", "streak_correct")
    assert streak_change(0, 2) == ("easier", "streak_wrong")
    assert streak_change(2, 1) is None
