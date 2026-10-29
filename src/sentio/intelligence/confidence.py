import logging
import math
from typing import List, Optional

logger = logging.getLogger(__name__)


class ConfidenceEngine:
    """
    Computes probabilistic confidence scores for learning concepts.
    Combines mastery, forgetting risk, review consistency, and credibility coefficients.
    """

    def __init__(self, lambda_decay: float = 0.05):
        self.lambda_decay = lambda_decay

    def calculate_confidence(
        self,
        mastery: float,
        last_attempt_at: Optional[float],
        current_time: float,
        attempts_count: int,
        quiz_scores: List[float],  # List of 1.0 (correct) or 0.0 (incorrect)
    ) -> float:
        """
        Formula:
          Confidence = Mastery * ForgettingDecay * ConsistencyScore * CredibilityWeight

        Where:
          1. ForgettingDecay = exp(-lambda * delta_t_days)
          2. ConsistencyScore = 1.0 - variance(quiz_scores) (if >= 2 attempts, else 1.0)
          3. CredibilityWeight = 1.0 - 1.0 / (attempts_count + 1)
        """
        # 1. Forgetting Decay
        forgetting_decay = 1.0
        if last_attempt_at is not None:
            delta_sec = max(0.0, current_time - last_attempt_at)
            delta_days = delta_sec / 86400.0
            forgetting_decay = math.exp(-self.lambda_decay * delta_days)

        # 2. Consistency Score
        consistency = 1.0
        if len(quiz_scores) >= 2:
            mean = sum(quiz_scores) / len(quiz_scores)
            variance = sum((x - mean) ** 2 for x in quiz_scores) / len(quiz_scores)
            # Higher variance (inconsistent performance) reduces confidence
            consistency = max(0.2, 1.0 - variance)

        # 3. Credibility Weight
        credibility = 1.0 - (1.0 / (attempts_count + 1.0)) if attempts_count > 0 else 0.0

        # Combine
        confidence = mastery * forgetting_decay * consistency * credibility
        return max(0.0, min(1.0, confidence))
