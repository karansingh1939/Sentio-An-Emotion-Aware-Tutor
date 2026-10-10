import logging
from typing import List

logger = logging.getLogger(__name__)


class MisconceptionEngine:
    """
    Detects conceptual misconceptions rather than simple low scores.
    Analyses quiz attempt text, student answers, and hint requests.
    """

    def detect_misconceptions(
        self, topic_id: str, quiz_attempts: List[dict], hints_requested: int, total_exchanges: int
    ) -> List[str]:
        """
        Analyzes patterns to identify specific misconceptions:
        1. Confusing base case with recursive step (recursion).
        2. Pseudo-force confusion (Newton's laws).
        3. Hint dependency (asking for hints too often).
        4. Infinite recursion confusion (getting stuck without a stopping condition).
        """
        misconceptions = []

        # 1. Hint Dependency Check
        if total_exchanges > 0:
            hint_ratio = hints_requested / total_exchanges
            if hint_ratio > 0.4:
                misconceptions.append("heavy_hint_dependency")

        # 2. Topic-specific Pattern Analysis
        wrong_attempts = [
            q for q in quiz_attempts if q.get("correct") == 0 or q.get("correct") is False
        ]

        if topic_id == "recursion":
            # Check if student confuses loops or base case stopping conditions
            infinite_keywords = ["infinite", "loop", "never stop", "stack overflow"]
            base_case_keywords = ["base case", "stopping condition", "stop condition", "stopping"]

            inf_hits = 0
            base_hits = 0

            for q in wrong_attempts:
                ans = str(q.get("student_answer", "")).lower()
                q_text = str(q.get("question_text", "")).lower()

                if any(k in ans for k in infinite_keywords):
                    inf_hits += 1
                if any(k in q_text for k in base_case_keywords) or "base" in ans:
                    base_hits += 1

            if inf_hits >= 2:
                misconceptions.append("recursion_infinite_loop_confusion")
            if base_hits >= 2:
                misconceptions.append("missing_base_case_comprehension")

        elif topic_id == "newtons_laws":
            # Check if student confuses Action-Reaction pairs or Normal Force directions
            normal_force_keywords = ["perpendicular", "gravity", "weight", "mg"]
            action_reaction_keywords = ["action", "reaction", "opposite", "equal"]

            normal_hits = 0
            act_react_hits = 0

            for q in wrong_attempts:
                ans = str(q.get("student_answer", "")).lower()

                if any(k in ans for k in normal_force_keywords):
                    normal_hits += 1
                if any(k in ans for k in action_reaction_keywords):
                    act_react_hits += 1

            if normal_hits >= 2:
                misconceptions.append("normal_force_direction_misconception")
            if act_react_hits >= 2:
                misconceptions.append("action_reaction_force_misconception")

        # 3. Patterned Mistake Check (more than 3 wrong attempts on same topic without progress)
        if len(wrong_attempts) >= 3 and len(quiz_attempts) == len(wrong_attempts):
            misconceptions.append("fundamental_topic_gap")

        return misconceptions
