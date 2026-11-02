"""The study mood is steady, honest about stale or unsure readings, and only nudges when sustained."""

from sentio.config import tutor_cfg
from sentio.emotion.policy import (
    BREAK_AFTER_SEC,
    MOOD_WINDOW_SEC,
    SIMPLER_AFTER_SEC,
    study_mood,
)
from sentio.session.models import EmotionEvent

NOW = 10_000.0
SURE = 0.9


def _event(at, state, confidence=SURE):
    return EmotionEvent(
        timestamp=NOW - at,
        emotion=state,
        learning_state=state,
        confidence=confidence,
        strategy_triggered="standard",
    )


def _steady(state, start, end=0, every=1, confidence=SURE):
    """One reading of a state each `every` seconds, from `start` to `end` seconds ago."""
    return [_event(at, state, confidence) for at in range(start, end - 1, -every)]


def test_no_readings_are_not_fresh_and_neutral():
    assert study_mood([], NOW) == {
        "learning_state": "neutral",
        "confidence": 0.0,
        "since": None,
        "nudge": None,
        "fresh": False,
    }


def test_stale_readings_are_not_fresh():
    mood = study_mood(_steady("struggling", 120, MOOD_WINDOW_SEC + 1), NOW)
    assert (mood["learning_state"], mood["fresh"], mood["nudge"]) == ("neutral", False, None)


def test_readings_after_now_are_ignored():
    assert study_mood([_event(-5, "engaged")], NOW)["fresh"] is False


def test_low_confidence_readings_are_ignored():
    unsure = tutor_cfg.EMOTION_CONFIDENCE_THRESHOLD - 0.01
    assert study_mood(_steady("frustrated", 25, confidence=unsure), NOW)["fresh"] is False

    mixed = _steady("frustrated", 25, confidence=unsure) + _steady("engaged", 10)
    mixed.sort(key=lambda event: event.timestamp)
    assert study_mood(mixed, NOW)["learning_state"] == "engaged"


def test_a_steady_state_is_reported_with_when_it_began():
    mood = study_mood(_steady("engaged", 10), NOW)
    assert mood == {
        "learning_state": "engaged",
        "confidence": SURE,
        "since": NOW - 10,
        "nudge": None,
        "fresh": True,
    }


def test_one_frame_cannot_leave_neutral():
    mood = study_mood([_event(1, "frustrated")], NOW)
    assert (mood["learning_state"], mood["fresh"], mood["since"]) == ("neutral", True, None)

    brief = tutor_cfg.STATE_PERSISTENCE_THRESHOLD - 1
    assert study_mood(_steady("anxious", brief), NOW)["learning_state"] == "neutral"


def test_a_flicker_does_not_change_the_state_or_restart_it():
    events = _steady("struggling", 25)
    events[10] = _event(15, "engaged")
    mood = study_mood(events, NOW)
    assert mood["learning_state"] == "struggling"
    assert mood["since"] == NOW - 25
    assert mood["nudge"] == "simpler"
    assert mood["confidence"] < SURE  # One reading of the window disagrees.


def test_the_majority_is_weighted_by_confidence():
    # Eight sure readings outweigh nine barely confident ones.
    events = _steady("curious", 20, 13, confidence=0.95) + _steady(
        "neutral", 12, 4, confidence=0.61
    )
    assert study_mood(events, NOW)["learning_state"] == "curious"


def test_a_tie_goes_to_the_newer_state():
    events = _steady("engaged", 20, 13) + _steady("curious", 12, 5)
    assert study_mood(events, NOW)["learning_state"] == "curious"


def test_a_switch_takes_over_once_it_holds_the_window_and_restarts_the_run():
    events = _steady("frustrated", 60, 21) + _steady("engaged", 20)
    mood = study_mood(events, NOW)
    assert (mood["learning_state"], mood["since"], mood["nudge"]) == ("engaged", NOW - 20, None)


def test_a_state_that_is_no_longer_current_does_not_nudge():
    # Still the window's majority, but the student has been calm for longer than a flicker.
    events = _steady("struggling", 30, 9) + _steady("neutral", 8)
    mood = study_mood(events, NOW)
    assert (mood["learning_state"], mood["nudge"]) == ("struggling", None)


def test_sustained_confusion_offers_a_simpler_explanation():
    for state in ("struggling", "frustrated", "anxious"):
        assert study_mood(_steady(state, SIMPLER_AFTER_SEC), NOW)["nudge"] == "simpler"
        assert study_mood(_steady(state, SIMPLER_AFTER_SEC - 1), NOW)["nudge"] is None


def test_sustained_distraction_offers_a_break():
    assert study_mood(_steady("disengaged", BREAK_AFTER_SEC, every=2), NOW)["nudge"] == "break"
    assert study_mood(_steady("disengaged", BREAK_AFTER_SEC - 2, every=2), NOW)["nudge"] is None


def test_a_camera_gap_restarts_the_run():
    events = _steady("disengaged", 120, 80) + _steady("disengaged", 30)
    mood = study_mood(events, NOW)
    assert (mood["since"], mood["nudge"]) == (NOW - 30, None)
