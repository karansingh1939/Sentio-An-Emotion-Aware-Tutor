import logging
import time
from collections import Counter, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sentio.config import tutor_cfg

logger = logging.getLogger(__name__)


class SessionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    TIMEDOUT = "timed_out"


@dataclass
class EmotionEvent:
    """A single timestamped emotion detection result."""

    timestamp: float  # Unix epoch
    emotion: str  # raw emotion label
    learning_state: str  # pedagogical state
    confidence: float
    strategy_triggered: str  # strategy that was active

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "dt": datetime.fromtimestamp(self.timestamp).isoformat(),
            "emotion": self.emotion,
            "learning_state": self.learning_state,
            "confidence": self.confidence,
            "strategy_triggered": self.strategy_triggered,
        }


@dataclass
class QuizAttempt:
    """Record of a single quiz question attempt."""

    timestamp: float
    topic: str
    difficulty: str
    correct: bool
    response_time_sec: float = 0.0
    question_preview: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DifficultyChange:
    """Log entry for a difficulty level change."""

    timestamp: float
    from_difficulty: str
    to_difficulty: str
    reason: str  # e.g. "3_correct_streak" | "struggling_state"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SessionAnalytics:
    """
    Post-session or live analytics report.
    Produced by SessionAnalyticsEngine.compute().
    """

    session_id: str
    student_id: str
    subject: str
    topic: str
    duration_minutes: float

    # Emotion analytics
    dominant_emotion: str
    dominant_learning_state: str
    emotion_distribution: Dict[str, float]  # {emotion: fraction}
    state_distribution: Dict[str, float]
    engagement_score: float  # 0.0 – 1.0  (weighted positivity)
    emotional_volatility: float  # 0.0 – 1.0  (std of state changes)

    # Learning analytics
    total_exchanges: int
    quiz_attempts: int
    quiz_accuracy: float  # 0.0 – 1.0
    difficulty_changes: int
    final_difficulty: str
    topics_covered: List[str]

    # Performance
    avg_response_latency_ms: float
    total_tokens_used: int

    # Flags
    needs_follow_up: bool  # True if ended frustrated/struggling

    def to_dict(self) -> dict:
        return asdict(self)

    def summary_text(self) -> str:
        return (
            f"Session {self.session_id[:8]}… | "
            f"{self.duration_minutes:.1f} min | "
            f"Engagement: {self.engagement_score:.0%} | "
            f"Quiz accuracy: {self.quiz_accuracy:.0%} | "
            f"Dominant state: {self.dominant_learning_state} | "
            f"Final difficulty: {self.final_difficulty}"
        )


class EmotionTimeline:
    """
    Ring buffer of EmotionEvents with analytics helpers.
    Stores up to MAX_EVENTS events; older events are dropped.
    """

    MAX_EVENTS = 2000

    # Engagement weights per learning state (for engagement score)
    ENGAGEMENT_WEIGHTS = {
        "engaged": 1.0,
        "curious": 0.9,
        "neutral": 0.5,
        "struggling": 0.3,
        "anxious": 0.2,
        "frustrated": 0.1,
        "disengaged": 0.0,
    }

    def __init__(self):
        self._events: deque = deque(maxlen=self.MAX_EVENTS)

    def record(self, event: EmotionEvent):
        self._events.append(event)

    def recent(self, n: int = 10) -> List[EmotionEvent]:
        """Return the last n events."""
        events = list(self._events)
        return events[-n:]

    def current_state(self) -> Optional[str]:
        """Most recent learning state."""
        if self._events:
            return self._events[-1].learning_state
        return None

    def state_persists(
        self, state: str, seconds: float = tutor_cfg.STATE_PERSISTENCE_THRESHOLD
    ) -> bool:
        """
        Returns True if the given state has been dominant
        for at least `seconds` continuously.
        """
        now = time.time()
        for event in reversed(list(self._events)):
            if now - event.timestamp > seconds:
                return event.learning_state == state
            if event.learning_state != state:
                return False
        return False

    def dominant_state(self, last_n: int = 50) -> str:
        """Most frequent learning state in the last n events."""
        recent = self.recent(last_n)
        if not recent:
            return "neutral"
        counts = Counter(e.learning_state for e in recent)
        return counts.most_common(1)[0][0]

    def emotion_distribution(self) -> Dict[str, float]:
        """Fraction of time in each emotion."""
        if not self._events:
            return {}
        counts = Counter(e.emotion for e in self._events)
        total = len(self._events)
        return {em: count / total for em, count in counts.items()}

    def state_distribution(self) -> Dict[str, float]:
        if not self._events:
            return {}
        counts = Counter(e.learning_state for e in self._events)
        total = len(self._events)
        return {st: count / total for st, count in counts.items()}

    def engagement_score(self) -> float:
        """
        Weighted average positivity score (0–1).
        Higher = more engaged/curious time.
        """
        if not self._events:
            return 0.5
        scores = [self.ENGAGEMENT_WEIGHTS.get(e.learning_state, 0.5) for e in self._events]
        return sum(scores) / len(scores)

    def emotional_volatility(self) -> float:
        """
        Measures how rapidly the student's state changes (0–1).
        High volatility may indicate difficulty or distractions.
        """
        events = list(self._events)
        if len(events) < 2:
            return 0.0
        changes = sum(
            1
            for i in range(1, len(events))
            if events[i].learning_state != events[i - 1].learning_state
        )
        return changes / (len(events) - 1)

    def all_as_dicts(self) -> List[dict]:
        return [e.to_dict() for e in self._events]

    def __len__(self):
        return len(self._events)


class QuizTracker:
    """
    Tracks quiz attempt history and consecutive streaks.
    The KnowledgeBase uses streaks to adapt difficulty.
    """

    def __init__(self):
        self._attempts: List[QuizAttempt] = []
        self.consecutive_correct: int = 0
        self.consecutive_wrong: int = 0

    def record(self, attempt: QuizAttempt):
        self._attempts.append(attempt)
        if attempt.correct:
            self.consecutive_correct += 1
            self.consecutive_wrong = 0
        else:
            self.consecutive_wrong += 1
            self.consecutive_correct = 0

    @property
    def total_attempts(self) -> int:
        return len(self._attempts)

    @property
    def total_correct(self) -> int:
        return sum(1 for a in self._attempts if a.correct)

    @property
    def accuracy(self) -> float:
        if not self._attempts:
            return 0.0
        return self.total_correct / self.total_attempts

    @property
    def recent_accuracy(self) -> float:
        """Accuracy over the last 5 attempts."""
        recent = self._attempts[-5:]
        if not recent:
            return 0.0
        return sum(1 for a in recent if a.correct) / len(recent)

    def all_as_dicts(self) -> List[dict]:
        return [a.to_dict() for a in self._attempts]


@dataclass
class Session:
    """
    Live in-memory state for a single tutoring session.
    One Session per student per learning session.
    """

    session_id: str
    student_id: str
    subject: str
    topic: str
    difficulty: str
    status: SessionStatus = SessionStatus.ACTIVE

    # Timestamps
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    closed_at: Optional[float] = None

    # Sub-trackers (not serialized directly)
    emotion_timeline: EmotionTimeline = field(default_factory=EmotionTimeline, repr=False)
    quiz_tracker: QuizTracker = field(default_factory=QuizTracker, repr=False)
    difficulty_log: List[DifficultyChange] = field(default_factory=list, repr=False)

    # Counters
    total_exchanges: int = 0
    total_tokens: int = 0
    response_latencies: List[float] = field(default_factory=list)

    # Topics covered in this session
    topics_covered: List[str] = field(default_factory=list)

    # Extra metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    summary: Optional[str] = None

    # ── Convenience Properties ──────────────────

    @property
    def duration_seconds(self) -> float:
        end = self.closed_at or time.time()
        return end - self.created_at

    @property
    def duration_minutes(self) -> float:
        return self.duration_seconds / 60.0

    @property
    def is_active(self) -> bool:
        return self.status == SessionStatus.ACTIVE

    @property
    def is_idle(self) -> bool:
        return (time.time() - self.updated_at) > tutor_cfg.IDLE_TIMEOUT_SEC

    @property
    def current_learning_state(self) -> str:
        if self.metadata and "learning_state" in self.metadata:
            return self.metadata["learning_state"]
        return self.emotion_timeline.current_state() or "neutral"

    @property
    def current_strategy(self) -> str:
        if self.metadata and "strategy" in self.metadata:
            return self.metadata["strategy"]
        return tutor_cfg.STRATEGY_MAP.get(self.current_learning_state, "standard")

    def touch(self):
        """Update last-activity timestamp."""
        self.updated_at = time.time()

    def add_topic(self, topic: str):
        if topic not in self.topics_covered:
            self.topics_covered.append(topic)

    def update_difficulty(self, new_difficulty: str, reason: str):
        if new_difficulty != self.difficulty:
            self.difficulty_log.append(
                DifficultyChange(
                    timestamp=time.time(),
                    from_difficulty=self.difficulty,
                    to_difficulty=new_difficulty,
                    reason=reason,
                )
            )
            self.difficulty = new_difficulty
            logger.info(
                f"Session {self.session_id[:8]} | "
                f"Difficulty: {self.difficulty_log[-1].from_difficulty} "
                f"→ {new_difficulty} ({reason})"
            )

    def record_exchange(self, tokens: int = 0, latency_ms: float = 0.0):
        self.total_exchanges += 1
        self.total_tokens += tokens
        if latency_ms > 0:
            self.response_latencies.append(latency_ms)
        self.touch()

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "student_id": self.student_id,
            "subject": self.subject,
            "topic": self.topic,
            "difficulty": self.difficulty,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "closed_at": self.closed_at,
            "duration_min": round(self.duration_minutes, 2),
            "total_exchanges": self.total_exchanges,
            "total_tokens": self.total_tokens,
            "topics_covered": self.topics_covered,
            "difficulty_log": [d.to_dict() for d in self.difficulty_log],
            "quiz_summary": {
                "attempts": self.quiz_tracker.total_attempts,
                "correct": self.quiz_tracker.total_correct,
                "accuracy": round(self.quiz_tracker.accuracy, 3),
            },
            "emotion_summary": {
                "dominant_state": self.emotion_timeline.dominant_state(),
                "engagement_score": round(self.emotion_timeline.engagement_score(), 3),
                "volatility": round(self.emotion_timeline.emotional_volatility(), 3),
                "distribution": self.emotion_timeline.state_distribution(),
            },
            "metadata": self.metadata,
            "summary": self.summary,
        }
