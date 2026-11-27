import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)


class ForgettingEngine:
    """
    Estimates forgetting risk and knowledge stability (memory half-life) for topics
    without reviewed flashcards, from quiz attempts, mastery and elapsed time. Topics with
    reviewed cards use the FSRS recall probability instead (see sentio.flashcards.fsrs).
    """

    def calculate_forgetting_risk(
        self,
        last_attempt_at: Optional[float],
        current_time: float,
        repetition_count: int,
        mastery: float,
    ) -> tuple[float, float]:
        """
        Calculates:
          1. Knowledge Stability (S) - expected memory half-life in days.
          2. Forgetting Risk (R) - probability of recall failure.

        Formula for Stability (S): S = max(1.0, 3.0 * repetition_count * mastery)

        Formula for Forgetting Risk (R):
          R = 1.0 - exp(-ln(2) * delta_t_days / S)
        """
        # 1. Estimate Knowledge Stability (Half-life in days, at least one day)
        stability = max(1.0, 3.0 * max(1, repetition_count) * mastery)

        # 2. Estimate Forgetting Risk
        if last_attempt_at is None:
            return 1.0, stability

        delta_sec = max(0.0, current_time - last_attempt_at)
        delta_days = delta_sec / 86400.0

        # R = 1.0 - 2^(-delta_days / S)
        risk = 1.0 - math.pow(2.0, -delta_days / stability)
        return max(0.0, min(1.0, risk)), stability
