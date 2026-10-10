import logging

from sentio.session.models import EmotionTimeline, Session, SessionAnalytics

logger = logging.getLogger(__name__)


class SessionAnalyticsEngine:
    """Computes analytics from a live or closed Session."""

    def compute(self, session: Session) -> SessionAnalytics:
        tl = session.emotion_timeline
        qt = session.quiz_tracker

        avg_latency = (
            sum(session.response_latencies) / len(session.response_latencies)
            if session.response_latencies
            else 0.0
        )

        last_state = tl.current_state() or "neutral"
        needs_follow_up = last_state in ("frustrated", "struggling", "anxious")

        return SessionAnalytics(
            session_id=session.session_id,
            student_id=session.student_id,
            subject=session.subject,
            topic=session.topic,
            duration_minutes=round(session.duration_minutes, 2),
            dominant_emotion=self._dominant_emotion(tl),
            dominant_learning_state=tl.dominant_state(),
            emotion_distribution=tl.emotion_distribution(),
            state_distribution=tl.state_distribution(),
            engagement_score=round(tl.engagement_score(), 3),
            emotional_volatility=round(tl.emotional_volatility(), 3),
            total_exchanges=session.total_exchanges,
            quiz_attempts=qt.total_attempts,
            quiz_accuracy=round(qt.accuracy, 3),
            difficulty_changes=len(session.difficulty_log),
            final_difficulty=session.difficulty,
            topics_covered=session.topics_covered,
            avg_response_latency_ms=round(avg_latency, 1),
            total_tokens_used=session.total_tokens,
            needs_follow_up=needs_follow_up,
        )

    def _dominant_emotion(self, tl: EmotionTimeline) -> str:
        dist = tl.emotion_distribution()
        if not dist:
            return "neutral"
        return max(dist, key=dist.get)
