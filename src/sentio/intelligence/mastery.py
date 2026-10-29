import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class MasteryEngine:
    """
    Calculates student topic mastery using multiple evidence sources (quizzes,
    flashcards, tutoring emotional timeline) and propagates mastery down the knowledge graph.
    """

    def __init__(self, w_quiz: float = 0.5, w_flashcard: float = 0.3, w_tutor: float = 0.2):
        self.w_quiz = w_quiz
        self.w_flashcard = w_flashcard
        self.w_tutor = w_tutor

    def calculate_topic_mastery(
        self, quiz_attempts: List[dict], flashcard_reviews: List[dict], emotion_events: List[dict]
    ) -> float:
        """
        Calculates topic-level mastery from quiz, flashcard, and tutoring timeline logs.
        Re-weights evidence dynamically if certain sources are missing.
        """
        evidences = {}

        # 1. Quiz evidence (success rate)
        if quiz_attempts:
            correct_count = sum(
                1 for q in quiz_attempts if q.get("correct") == 1 or q.get("correct") is True
            )
            evidences["quiz"] = correct_count / len(quiz_attempts)

        # 2. Flashcard evidence: mean FSRS recall probability of reviewed cards
        recall = [
            f["recall_probability"]
            for f in flashcard_reviews
            if f.get("recall_probability") is not None
        ]
        if recall:
            evidences["flashcard"] = sum(recall) / len(recall)

        # 3. Tutoring session evidence (fraction of engaged/curious/neutral vs struggling/anxious/frustrated)
        if emotion_events:
            total_states = len(emotion_events)
            negative_states = sum(
                1
                for e in emotion_events
                if e.get("learning_state") in ("struggling", "anxious", "frustrated")
            )
            evidences["tutor"] = 1.0 - (negative_states / total_states)

        # Calculate weighted sum based on available evidence
        if not evidences:
            return 0.0

        available_sources = list(evidences.keys())
        raw_weights = {"quiz": self.w_quiz, "flashcard": self.w_flashcard, "tutor": self.w_tutor}

        # Filter active weights
        active_weights = {k: raw_weights[k] for k in available_sources}
        total_weight = sum(active_weights.values())

        if total_weight > 0:
            normalized_weights = {k: w / total_weight for k, w in active_weights.items()}
        else:
            normalized_weights = {k: 1.0 / len(available_sources) for k in available_sources}

        mastery = sum(evidences[k] * normalized_weights[k] for k in available_sources)
        return max(0.0, min(1.0, mastery))

    def propagate_mastery(
        self, raw_mastery: Dict[str, float], prerequisites: Dict[str, List[str]]
    ) -> Dict[str, float]:
        """
        Applies prerequisite limits to downstream mastery targets.
        If a prerequisite topic has low mastery, the downstream target's mastery
        estimate is scaled down to reflect weak foundational understanding.
        """
        propagated = dict(raw_mastery)
        for topic, prereqs in prerequisites.items():
            if not prereqs:
                continue
            # Calculate the minimum prerequisite mastery
            prereq_mastery_list = [raw_mastery.get(p, 0.0) for p in prereqs]
            if prereq_mastery_list:
                min_prereq_mastery = min(prereq_mastery_list)
                # Soft scaling factor: if prereqs are weak, scale downstream mastery
                # e.g., if min_prereq is 0.2, then scale downstream mastery by 0.6 + 0.4 * 0.2 = 0.68
                scale = 0.5 + 0.5 * min_prereq_mastery
                if topic in propagated:
                    propagated[topic] = propagated[topic] * scale
        return propagated
