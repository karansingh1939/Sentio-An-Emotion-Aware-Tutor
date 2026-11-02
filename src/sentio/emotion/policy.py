"""How camera emotion readings become a study mood: steady, honest and tone-only.

Phase 4 contract stub: the ML engineer implements study_mood (docs/project/phase-4-slide-study.md).
"""

MOOD_WINDOW_SEC = 30


def study_mood(events, now):
    """The learner's recent study mood from EmotionEvents (oldest first)."""
    return {
        "learning_state": "neutral",
        "confidence": 0.0,
        "since": None,
        "nudge": None,
        "fresh": False,
    }
