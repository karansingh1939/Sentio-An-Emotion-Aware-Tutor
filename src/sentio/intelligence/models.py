from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class LearnerModel:
    """
    Continually updated multidimensional state representation of a student.
    Covers mastery, retention, interaction behaviors, and preferences.
    """

    student_id: str
    overall_mastery: float = 0.0
    topic_mastery: Dict[str, float] = field(default_factory=dict)
    confidence: Dict[str, float] = field(default_factory=dict)
    learning_velocity: float = 0.0  # Average mastery change rate per day/session
    forgetting_risk: Dict[str, float] = field(
        default_factory=dict
    )  # Expected probability of recall loss
    knowledge_stability: Dict[str, float] = field(
        default_factory=dict
    )  # Calculated memory half-life (S) in days
    weak_concepts: List[str] = field(default_factory=list)
    strong_concepts: List[str] = field(default_factory=list)
    misconceptions: Dict[str, List[str]] = field(
        default_factory=dict
    )  # topic_id -> list of detected misconceptions
    review_priorities: List[str] = field(
        default_factory=list
    )  # Ordered list of topic IDs to review
    learning_streak: int = 0
    avg_response_quality: float = 0.0  # Derived from quiz correct percentage
    hint_frequency: float = 0.0  # Hints requested per exchange
    tutor_intervention_frequency: float = 0.0  # Percentage of exchanges requiring strategy shift
    preferred_explanation_style: str = "standard"  # standard | analogy | simplify | challenge
    preferred_difficulty: str = "intermediate"
    engagement_score: float = 0.5
    cognitive_load_estimate: float = 0.0  # Calculated from volatility & response latency
    session_consistency: float = 1.0  # Ratio of active to scheduled sessions
    readiness_for_assessment: Dict[str, bool] = field(default_factory=dict)  # topic_id -> ready
    historical_progress_timeline: List[Dict[str, Any]] = field(
        default_factory=list
    )  # list of session snapshots

    def to_dict(self) -> dict:
        return {
            "student_id": self.student_id,
            "overall_mastery": round(self.overall_mastery, 3),
            "topic_mastery": {k: round(v, 3) for k, v in self.topic_mastery.items()},
            "confidence": {k: round(v, 3) for k, v in self.confidence.items()},
            "learning_velocity": round(self.learning_velocity, 3),
            "forgetting_risk": {k: round(v, 3) for k, v in self.forgetting_risk.items()},
            "knowledge_stability": {k: round(v, 1) for k, v in self.knowledge_stability.items()},
            "weak_concepts": self.weak_concepts,
            "strong_concepts": self.strong_concepts,
            "misconceptions": self.misconceptions,
            "review_priorities": self.review_priorities,
            "learning_streak": self.learning_streak,
            "avg_response_quality": round(self.avg_response_quality, 3),
            "hint_frequency": round(self.hint_frequency, 3),
            "tutor_intervention_frequency": round(self.tutor_intervention_frequency, 3),
            "preferred_explanation_style": self.preferred_explanation_style,
            "preferred_difficulty": self.preferred_difficulty,
            "engagement_score": round(self.engagement_score, 3),
            "cognitive_load_estimate": round(self.cognitive_load_estimate, 3),
            "session_consistency": round(self.session_consistency, 3),
            "readiness_for_assessment": self.readiness_for_assessment,
            "historical_progress_timeline": self.historical_progress_timeline,
        }


@dataclass
class StudyRecommendation:
    """An actionable, explained educational task recommended for a student."""

    topic_id: str
    action: str  # review_flashcards | start_tutoring | take_quiz | review_prerequisites | increase_challenge
    priority_score: float
    explanation: str

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "action": self.action,
            "priority_score": round(self.priority_score, 3),
            "explanation": self.explanation,
        }


@dataclass
class SessionSummaryReport:
    """Pedagogical progress and engagement overview for a finished session."""

    session_id: str
    student_id: str
    subject: str
    duration_min: float
    topics_covered: List[str]
    quiz_performance: Dict[str, Any]
    dominant_emotion: str
    emotion_trends: Dict[str, float]
    recommended_next_actions: List[Dict[str, Any]]
    estimated_retention: float
    next_review_schedule: Dict[str, float]  # topic_id -> epoch timestamp

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "student_id": self.student_id,
            "subject": self.subject,
            "duration_min": round(self.duration_min, 2),
            "topics_covered": self.topics_covered,
            "quiz_performance": self.quiz_performance,
            "dominant_emotion": self.dominant_emotion,
            "emotion_trends": {k: round(v, 3) for k, v in self.emotion_trends.items()},
            "recommended_next_actions": self.recommended_next_actions,
            "estimated_retention": round(self.estimated_retention, 3),
            "next_review_schedule": self.next_review_schedule,
        }
