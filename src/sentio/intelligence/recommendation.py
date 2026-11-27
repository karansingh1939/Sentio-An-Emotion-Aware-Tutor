import logging
from typing import Dict, List

from sentio.intelligence.models import StudyRecommendation

logger = logging.getLogger(__name__)


def _name(topic_id):
    """A topic as the learner named it; old ids written with underscores read as words."""
    return topic_id.replace("_", " ")


class RecommendationEngine:
    """
    Evaluates concept mastery, confidence, and database signals to recommend
    optimal study actions (reviewing flashcards, starting tutoring, taking quizzes, etc.).
    """

    def generate_recommendations(
        self,
        student_id: str,
        topic_id: str,
        mastery: float,
        confidence: float,
        due_flashcards_count: int,
        has_deck: bool,
        prereqs: List[str],
        prereq_mastery: Dict[str, float],
    ) -> List[StudyRecommendation]:
        """
        Evaluates topic stats and returns study recommendations with structured reasoning.
        """
        recommendations = []

        # 1. Check if prerequisite concepts are weak
        weak_prereqs = [p for p in prereqs if prereq_mastery.get(p, 0.0) < 0.6]
        if weak_prereqs:
            for p in weak_prereqs:
                p_mast = prereq_mastery.get(p, 0.0)
                priority = 0.9 * (1.0 - p_mast)
                recommendations.append(
                    StudyRecommendation(
                        topic_id=p,
                        action="review_prerequisites",
                        priority_score=priority,
                        explanation=(
                            f"We recommend reviewing the prerequisite concept '{_name(p)}' "
                            f"because its mastery is low ({p_mast:.0%}), which is holding back your understanding "
                            f"of the downstream concept '{_name(topic_id)}'."
                        ),
                    )
                )

        # 2. Check if flashcards are due for review
        if due_flashcards_count > 0:
            priority = 0.8 * (1.0 - confidence) + 0.3
            recommendations.append(
                StudyRecommendation(
                    topic_id=topic_id,
                    action="review_flashcards",
                    priority_score=priority,
                    explanation=(
                        f"You have {due_flashcards_count} flashcards due for review in '{_name(topic_id)}'. "
                        f"Reviewing these now will strengthen your memory retention (current confidence: {confidence:.0%})."
                    ),
                )
            )

        # 3. Start Tutoring recommendation
        if mastery < 0.5:
            priority = 0.85 * (1.0 - mastery)
            recommendations.append(
                StudyRecommendation(
                    topic_id=topic_id,
                    action="start_tutoring",
                    priority_score=priority,
                    explanation=(
                        f"We recommend starting an interactive tutoring session on '{_name(topic_id)}' "
                        f"because your mastery score ({mastery:.0%}) is below the required baseline. "
                        f"The tutor explains it step by step from your notes."
                    ),
                )
            )

        # 4. Generate new flashcards if none exist
        if not has_deck and mastery > 0.0:
            priority = 0.6
            recommendations.append(
                StudyRecommendation(
                    topic_id=topic_id,
                    action="generate_new_flashcards",
                    priority_score=priority,
                    explanation=(
                        f"We recommend generating a new flashcard deck for '{_name(topic_id)}' "
                        f"to initialize active recall review loops for key definitions."
                    ),
                )
            )

        # 5. Take a Quiz to test progress
        if mastery >= 0.5 and confidence < 0.7:
            priority = 0.7 * (1.0 - confidence)
            recommendations.append(
                StudyRecommendation(
                    topic_id=topic_id,
                    action="take_quiz",
                    priority_score=priority,
                    explanation=(
                        f"We recommend taking a short quiz on '{_name(topic_id)}' "
                        f"to test your understanding and boost your concept confidence."
                    ),
                )
            )

        # 6. Increase challenge level
        if mastery >= 0.85 and confidence >= 0.8:
            priority = 0.5 + (mastery - 0.8)
            recommendations.append(
                StudyRecommendation(
                    topic_id=topic_id,
                    action="increase_challenge",
                    priority_score=priority,
                    explanation=(
                        f"Excellent! Your mastery on '{_name(topic_id)}' is {mastery:.0%}. "
                        f"We recommend stepping up the difficulty to challenge yourself with advanced extensions."
                    ),
                )
            )

        # Sort recommendations by priority score descending
        recommendations.sort(key=lambda x: x.priority_score, reverse=True)
        return recommendations
