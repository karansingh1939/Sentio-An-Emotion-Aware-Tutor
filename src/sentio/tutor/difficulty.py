"""The one place that decides when a session's difficulty changes.

Difficulty is what the learner chose. It changes only when:
1. the learner asks for it in chat ("make it harder", "explain it more simply"), or
2. quiz answers in the session show it: 3 correct in a row steps up, 2 wrong steps down.
Quiz steps are skipped while the learner has pinned a level (set it themselves or used
Undo); an explicit request always applies and clears the pin. Emotion and confusion
change only the tutor's tone, never the level.

Requests are matched as phrases addressed to the tutor, so questions about the content
("Why is diamond harder than graphite?") do not change anything.
"""

import re

LEVELS = ("beginner", "intermediate", "advanced")
STREAK_UP = 3
STREAK_DOWN = 2

_SUBJECT = r"(?:(?:it|this|that|these|those|the)(?: (?:questions?|examples?|explanations?|ones?))?)"
_HARDER = re.compile(
    rf"\b(?:make|can you make|could you make)\s+{_SUBJECT}\s+(?:a bit\s+|a little\s+)?"
    r"(?:harder|more (?:difficult|advanced|challenging))\b"
    r"|\b(?:it'?s|this is|that'?s|these are|this was|that was)\s+(?:too|way too|a bit too)\s+easy\b"
    r"|\bchallenge me\b"
    r"|\b(?:give|ask|show) me\s+(?:a\s+|some\s+)?(?:harder|more (?:difficult|advanced|challenging))\b"
    r"|\b(?:harder|more (?:difficult|advanced|challenging)) (?:questions?|examples?|problems?|ones?)\b",
    re.IGNORECASE,
)
_EASIER = re.compile(
    rf"\b(?:make|can you make|could you make)\s+{_SUBJECT}\s+(?:a bit\s+|a little\s+)?(?:easier|simpler)\b"
    r"|\b(?:it'?s|this is|that'?s|these are|this was|that was|i find (?:it|this))\s+"
    r"(?:too|way too|a bit too)\s+(?:hard|difficult|complex|complicated)\b"
    r"|\b(?:explain|say|put)\b[^.?!]{0,25}?\b(?:more simply|simpler|easier|in simple(?:r)? (?:terms|words))\b"
    r"|\bsimplify (?:it|this|that)\b"
    r"|\b(?:give|ask|show) me\s+(?:an?\s+|some\s+)?(?:easier|simpler)\b"
    r"|\b(?:easier|simpler) (?:questions?|examples?|problems?|version|explanation|ones?)\b",
    re.IGNORECASE,
)
_CONFUSED = re.compile(
    r"\bi(?:'m| am)\s+(?:so\s+|really\s+)?(?:lost|confused)\b"
    r"|\bi (?:don'?t|do not) (?:understand|get it)\b"
    r"|\b(?:explain|say)\b[^.?!]{0,15}?\b(?:another|a different) way\b"
    r"|\bexplain (?:it |this |that )?differently\b"
    r"|\b(?:it|this|that) makes no sense\b",
    re.IGNORECASE,
)

REASONS = {
    "request_harder": "you asked for harder",
    "request_easier": "you asked for simpler",
    "streak_correct": f"{STREAK_UP} correct answers in a row",
    "streak_wrong": f"{STREAK_DOWN} wrong answers in a row",
    "learner_choice": "you chose this level",
}


def requested_change(message):
    """The direction the learner explicitly asked for ("harder" or "easier"), or None."""
    if _EASIER.search(message or ""):
        return "easier"
    if _HARDER.search(message or ""):
        return "harder"
    return None


def asks_for_another_explanation(message):
    """The learner says they are confused: re-explain, without changing the level."""
    return bool(_CONFUSED.search(message or ""))


def step(level, direction):
    index = LEVELS.index(level) if level in LEVELS else 1
    index += 1 if direction == "harder" else -1
    return LEVELS[max(0, min(len(LEVELS) - 1, index))]


def streak_change(correct_streak, wrong_streak):
    """(direction, reason) when a run of quiz answers should move the level, else None."""
    if correct_streak >= STREAK_UP:
        return "harder", "streak_correct"
    if wrong_streak >= STREAK_DOWN:
        return "easier", "streak_wrong"
    return None


def describe(previous, current, reason):
    """The change as shown to the learner, with what Undo would restore."""
    return {
        "from": previous,
        "to": current,
        "reason": reason,
        "reason_text": REASONS.get(reason, reason),
    }
