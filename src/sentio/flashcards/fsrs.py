"""FSRS memory model for flashcard scheduling.

FSRS (Free Spaced Repetition Scheduler, version 5) describes each card with two numbers:
stability S, the number of days until the chance of recalling it falls to 90%, and
difficulty D, from 1 (easy) to 10 (hard). Recall probability decays as a power curve,
R(t) = (1 + FACTOR * t / S) ** DECAY. Each rating updates S and D with the published
default parameters, and the next review is set for when R reaches DESIRED_RETENTION.
"""

import math

# Default FSRS-5 parameters, fitted by the open-spaced-repetition project on review logs.
W = (
    0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046, 1.54575, 0.1192,
    1.01925, 1.9395, 0.11, 0.29605, 2.2698, 0.2315, 2.9898, 0.51655, 0.6621,
)  # fmt: skip
DECAY = -0.5
FACTOR = 0.9 ** (1 / DECAY) - 1
DESIRED_RETENTION = 0.9
MAX_INTERVAL_DAYS = 3650
DAY = 86400
AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4
RATINGS = {"again": AGAIN, "hard": HARD, "good": GOOD, "easy": EASY}


def rating_from_quality(quality):
    """Map the 0-5 review score the API accepts onto the four FSRS ratings."""
    return AGAIN if quality < 3 else quality - 1


def retrievability(elapsed_days, stability):
    return (1 + FACTOR * max(0.0, elapsed_days) / stability) ** DECAY


def interval_days(stability):
    days = stability / FACTOR * (DESIRED_RETENTION ** (1 / DECAY) - 1)
    return min(MAX_INTERVAL_DAYS, max(1, round(days)))


def _initial_difficulty(rating):
    return W[4] - math.exp(W[5] * (rating - 1)) + 1


def _clamp(difficulty):
    return min(10.0, max(1.0, difficulty))


def memory_state(card):
    """Return (stability, difficulty, last_review_at), or None for a card never reviewed.

    Cards last scheduled by the earlier SM-2 scheduler are converted on their next review:
    the last interval becomes stability and the ease factor sets difficulty.
    """
    if card.get("stability"):
        return card["stability"], card["difficulty"], card["last_review_at"]
    interval = card.get("interval_days") or 0
    if interval <= 0:
        return None
    difficulty = _clamp(11 - 2 * (card.get("ease_factor") or 2.5))
    return float(interval), difficulty, card["next_review_at"] - interval * DAY


def review(card, rating, now):
    """Return the card's (stability, difficulty) after a rating given at time now."""
    state = memory_state(card)
    if state is None:
        return W[rating - 1], _clamp(_initial_difficulty(rating))
    stability, difficulty, last_review_at = state
    elapsed = (now - last_review_at) / DAY
    recall = retrievability(elapsed, stability)
    if elapsed < 1:
        stability *= math.exp(W[17] * (rating - 3 + W[18]))
    elif rating == AGAIN:
        relearned = (
            W[11]
            * difficulty ** -W[12]
            * ((stability + 1) ** W[13] - 1)
            * math.exp(W[14] * (1 - recall))
        )
        stability = min(stability, relearned)
    else:
        bonus = W[15] if rating == HARD else W[16] if rating == EASY else 1
        growth = (
            math.exp(W[8])
            * (11 - difficulty)
            * stability ** -W[9]
            * (math.exp(W[10] * (1 - recall)) - 1)
        )
        stability *= 1 + growth * bonus
    difficulty += -W[6] * (rating - 3) * (10 - difficulty) / 9
    difficulty = W[7] * _initial_difficulty(EASY) + (1 - W[7]) * difficulty
    return max(0.01, stability), _clamp(difficulty)


def next_intervals(card, now):
    """Days until the next review for each rating, shown on the review buttons."""
    return {name: interval_days(review(card, rating, now)[0]) for name, rating in RATINGS.items()}


def recall_probability(card, now):
    """Chance the learner recalls the card now, or None if it was never reviewed."""
    state = memory_state(card)
    if state is None:
        return None
    stability, _, last_review_at = state
    return retrievability((now - last_review_at) / DAY, stability)
