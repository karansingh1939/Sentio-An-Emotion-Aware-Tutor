import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ExplanationEngine:
    """
    Generates human-readable, structured explanations for study recommendations
    and tutoring adaptations.
    """

    def explain_recommendation(self, action: str, topic_id: str, details: Dict[str, Any]) -> str:
        """
        Formulates a structured explanation for a given study recommendation action.
        """
        topic_name = topic_id.replace("_", " ").title()

        if action == "review_prerequisites":
            prereq = details.get("prerequisite", "foundational concepts")
            prereq_name = prereq.replace("_", " ").title()
            mastery = details.get("prereq_mastery", 0.0)
            return (
                f"We recommend reviewing '{prereq_name}' because your mastery score is low ({mastery:.0%}), "
                f"which acts as a blocker for downstream concepts in '{topic_name}'."
            )

        elif action == "review_flashcards":
            due_count = details.get("due_count", 1)
            confidence = details.get("confidence", 0.0)
            return (
                f"You have {due_count} flashcards due for review in '{topic_name}'. "
                f"Practicing these now prevents memory decay (current confidence is {confidence:.0%})."
            )

        elif action == "start_tutoring":
            mastery = details.get("mastery", 0.0)
            return (
                f"Your current mastery of '{topic_name}' is {mastery:.0%}. "
                f"An interactive tutoring session will explain key concepts step-by-step using worked examples."
            )

        elif action == "take_quiz":
            confidence = details.get("confidence", 0.0)
            return (
                f"Taking a quiz on '{topic_name}' will test your active recall and "
                f"reinforce your concept confidence (currently at {confidence:.0%})."
            )

        elif action == "increase_challenge":
            mastery = details.get("mastery", 0.0)
            return (
                f"With a high mastery of {mastery:.0%} in '{topic_name}', you are ready "
                f"for advanced challenges. We recommend increasing the difficulty level."
            )

        elif action == "generate_new_flashcards":
            return (
                f"You have studied concepts in '{topic_name}', but do not have a flashcard deck yet. "
                f"Generating a deck will initialize the spaced repetition schedule."
            )

        return f"Study recommendation for '{topic_name}' based on current learner model stats."
