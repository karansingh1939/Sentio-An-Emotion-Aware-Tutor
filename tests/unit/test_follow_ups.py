"""A follow-up is searched together with the question it follows."""

from types import SimpleNamespace

import pytest

from sentio.tutor.difficulty import asks_for_another_explanation, follows_up


@pytest.mark.parametrize(
    "message",
    [
        "no i didnt understand",
        "I didn't get it",
        "still not clear",
        "explain it again",
        "why?",
        "give an example",
        "what about stride 1?",
        "make it simpler",
    ],
)
def test_replies_that_point_back_are_follow_ups(message):
    assert follows_up(message)


@pytest.mark.parametrize(
    "message",
    [
        "What is a CSV file?",
        "What are the layers of cloud-based AIoT?",
        "How do I open a MAT file in Python?",
    ],
)
def test_new_questions_are_not_follow_ups(message):
    assert not follows_up(message)


def test_didnt_understand_asks_for_another_explanation():
    assert asks_for_another_explanation("no i didnt understand")
    assert not asks_for_another_explanation("What does understand mean in NLP?")


def test_a_follow_up_is_searched_with_the_previous_question():
    from sentio.tutor.orchestrator import SentioOrchestrator

    orchestrator = SentioOrchestrator.__new__(SentioOrchestrator)
    orchestrator.tutor_agent = SimpleNamespace()
    history = [
        {"role": "user", "content": "What output size does a 7x7 input give with stride 2?"},
        {"role": "assistant", "content": "3x3 [cnn.pdf Page 96]"},
    ]
    state = {"user_message": "no i didnt understand", "history": history, "session_id": "s"}
    assert orchestrator._search_query(state) == (
        "What output size does a 7x7 input give with stride 2? no i didnt understand"
    )
    fresh = {**state, "user_message": "What is a CSV file?"}
    assert orchestrator._search_query(fresh) == "What is a CSV file?"
