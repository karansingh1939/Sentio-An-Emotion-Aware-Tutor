import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ProgressEngine:
    """
    Tracks and parses historical mastery progress data to determine velocity,
    concept stability, and learning trends.
    """

    def calculate_progress_metrics(
        self, timeline: List[Dict[str, Any]], current_mastery: float
    ) -> Dict[str, Any]:
        """
        Processes session progress snapshots to compute:
          - overall_gain: overall mastery change.
          - velocity: rate of mastery change per session.
          - trend: positive | stable | declining.
          - weekly_velocity: average change rate in recent timeline points.
        """
        metrics = {
            "overall_gain": 0.0,
            "velocity": 0.0,
            "trend": "stable",
            "weekly_gain": 0.0,
            "concept_stability_average": 0.5,
        }

        if not timeline:
            return metrics

        # Sort timeline by timestamp ascending
        sorted_timeline = sorted(timeline, key=lambda x: x.get("timestamp", 0.0))

        first_point = sorted_timeline[0]
        initial_mastery = first_point.get("overall_mastery", 0.0)

        # 1. Compute Overall Gain
        metrics["overall_gain"] = current_mastery - initial_mastery

        # 2. Compute Learning Velocity (delta mastery per session or timeline entry)
        if len(sorted_timeline) > 1:
            metrics["velocity"] = (current_mastery - initial_mastery) / len(sorted_timeline)
        else:
            metrics["velocity"] = current_mastery - initial_mastery

        # 3. Compute Weekly Gain (last 3 timeline points as proxy for a week of activity)
        if len(sorted_timeline) >= 3:
            recent_point = sorted_timeline[-3]
            metrics["weekly_gain"] = current_mastery - recent_point.get("overall_mastery", 0.0)
        else:
            metrics["weekly_gain"] = metrics["overall_gain"]

        # 4. Set Trend Label
        if metrics["velocity"] > 0.02:
            metrics["trend"] = "positive"
        elif metrics["velocity"] < -0.02:
            metrics["trend"] = "declining"
        else:
            metrics["trend"] = "stable"

        # 5. Concept stability (average half-life of memory stored on topics)
        stabilities = []
        for pt in sorted_timeline:
            stab = pt.get("knowledge_stability", {})
            if stab:
                stabilities.extend(stab.values())
        if stabilities:
            metrics["concept_stability_average"] = sum(stabilities) / len(stabilities)

        return metrics
