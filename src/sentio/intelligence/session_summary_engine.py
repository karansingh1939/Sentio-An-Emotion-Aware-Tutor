import logging
import time
from collections import Counter
from typing import Dict, List

from sentio.intelligence.models import SessionSummaryReport

logger = logging.getLogger(__name__)


class SessionSummaryEngine:
    """
    Analyzes session logs (emotion timelines, quiz attempts, duration) to compile
    a SessionSummaryReport detailing topics, retention estimates, and emotion trends.
    """

    def compile_summary(
        self,
        session_id: str,
        student_id: str,
        subject: str,
        duration_min: float,
        topics_covered: List[str],
        quiz_attempts: List[dict],
        emotion_events: List[dict],
        topic_retention: Dict[str, float],
        next_reviews: Dict[str, float],
        recommendations: List[dict],
    ) -> SessionSummaryReport:
        """
        Synthesizes active session logs into a structured summary report.
        """
        # 1. Quiz performance aggregation
        quiz_summary = {
            "attempts": len(quiz_attempts),
            "correct": sum(
                1 for q in quiz_attempts if q.get("correct") == 1 or q.get("correct") is True
            ),
            "accuracy": 0.0,
        }
        if quiz_summary["attempts"] > 0:
            quiz_summary["accuracy"] = quiz_summary["correct"] / quiz_summary["attempts"]

        # 2. Emotion trends tallies
        emotion_trends = {}
        dominant_emotion = "neutral"
        if emotion_events:
            states = [e.get("learning_state", "neutral") for e in emotion_events]
            counts = Counter(states)
            total = len(states)
            emotion_trends = {k: v / total for k, v in counts.items()}
            dominant_emotion = counts.most_common(1)[0][0]

        # 3. Estimated retention (average retention across topics covered)
        retentions = [1.0 - topic_retention.get(t, 0.0) for t in topics_covered]
        estimated_retention = sum(retentions) / len(retentions) if retentions else 1.0

        # 4. Next review schedule (topics covered -> timestamp)
        next_review_schedule = {}
        for t in topics_covered:
            next_review_schedule[t] = next_reviews.get(t, time.time() + 86400.0)

        return SessionSummaryReport(
            session_id=session_id,
            student_id=student_id,
            subject=subject,
            duration_min=duration_min,
            topics_covered=topics_covered,
            quiz_performance=quiz_summary,
            dominant_emotion=dominant_emotion,
            emotion_trends=emotion_trends,
            recommended_next_actions=recommendations,
            estimated_retention=estimated_retention,
            next_review_schedule=next_review_schedule,
        )
