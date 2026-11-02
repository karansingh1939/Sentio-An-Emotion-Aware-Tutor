"""How camera emotion readings become a study mood: steady, honest and tone-only.

study_mood is deterministic: the same readings and the same `now` give the same mood.

- Only confident readings (tutor_cfg.EMOTION_CONFIDENCE_THRESHOLD) count, and only those in
  the last MOOD_WINDOW_SEC choose the state, by confidence-weighted majority.
- A state other than "neutral" must have been seen for STATE_PERSISTENCE_THRESHOLD seconds,
  so one frame cannot flip the tone.
- The run of a state ends at a camera gap longer than the window, or when another state is
  seen for the persistence threshold; shorter flickers do not end it.
- `nudge` offers a simpler explanation after sustained confusion and a break after sustained
  distraction. The mood changes only the tone, never difficulty or sources.
"""

from sentio.config import tutor_cfg

MOOD_WINDOW_SEC = 30
SIMPLER_AFTER_SEC = 20  # Struggling, frustrated or anxious this long: offer a simpler explanation.
BREAK_AFTER_SEC = 60  # Disengaged this long: offer a short break.
CONFUSED_STATES = ("struggling", "frustrated", "anxious")


def study_mood(events, now):
    """The learner's recent study mood from EmotionEvents (oldest first)."""
    readings = [
        event
        for event in events
        if event.confidence >= tutor_cfg.EMOTION_CONFIDENCE_THRESHOLD and event.timestamp <= now
    ]
    recent = [event for event in readings if now - event.timestamp <= MOOD_WINDOW_SEC]
    if not recent:
        return _mood("neutral", 0.0, None, None, fresh=False)

    weights = _weights(recent)
    state = max(weights, key=weights.get)
    since, last, current = _run(_stretches(readings), state)
    if state != "neutral" and last - since < tutor_cfg.STATE_PERSISTENCE_THRESHOLD:
        state, since, current = "neutral", None, False
    confidence = round(weights.get(state, (0.0,))[0] / len(recent), 3)
    nudge = _nudge(state, last - since) if current else None
    return _mood(state, confidence, since, nudge, fresh=True)


def _mood(state, confidence, since, nudge, fresh):
    return {
        "learning_state": state,
        "confidence": confidence,
        "since": since,
        "nudge": nudge,
        "fresh": fresh,
    }


def _weights(readings):
    """Summed confidence per state, then the latest time seen, so a tie goes to the newer state."""
    weights = {}
    for event in readings:
        total = weights.get(event.learning_state, (0.0, 0.0))[0]
        weights[event.learning_state] = (total + event.confidence, event.timestamp)
    return weights


def _stretches(readings):
    """Consecutive readings of one state, without a camera gap, as [state, first, last]."""
    stretches = []
    for event in readings:
        last = stretches[-1] if stretches else None
        if (
            last
            and last[0] == event.learning_state
            and event.timestamp - last[2] <= MOOD_WINDOW_SEC
        ):
            last[2] = event.timestamp
        else:
            stretches.append([event.learning_state, event.timestamp, event.timestamp])
    return stretches


def _run(stretches, state):
    """(since, last, current) for the latest run of a state.

    `current` is False when another state has since been seen for the persistence threshold.
    """
    since = last = None
    current = True
    newer = None  # When the next newer stretch began, to find camera gaps.
    for name, first, end in reversed(stretches):
        if newer is not None and newer - end > MOOD_WINDOW_SEC:
            break
        newer = first
        if name == state:
            since, last = first, last if last is not None else end
        elif end - first >= tutor_cfg.STATE_PERSISTENCE_THRESHOLD:
            if since is not None:
                break
            current = False
    return since, last, current


def _nudge(state, persisted):
    if state in CONFUSED_STATES and persisted >= SIMPLER_AFTER_SEC:
        return "simpler"
    if state == "disengaged" and persisted >= BREAK_AFTER_SEC:
        return "break"
    return None
