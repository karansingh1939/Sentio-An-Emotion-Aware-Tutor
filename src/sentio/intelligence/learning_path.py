import logging
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


class LearningPathEngine:
    """
    Constructs personalized learning paths by topologically sorting topics based on
    prerequisite graphs and evaluating student readiness.
    """

    def sequence_topics(
        self,
        all_topics: List[str],
        prerequisites: List[Tuple[str, str]],  # list of (parent_prereq, child_topic)
    ) -> List[str]:
        """
        Topologically sorts a list of topics. Prerequisite parents always precede their child topics.
        Handles cyclic dependencies gracefully by falling back to original order.
        """
        # Build adjacency list & in-degree counts
        graph: Dict[str, Set[str]] = {t: set() for t in all_topics}
        in_degree: Dict[str, int] = {t: 0 for t in all_topics}

        for parent, child in prerequisites:
            if parent in graph and child in graph:
                if child not in graph[parent]:
                    graph[parent].add(child)
                    in_degree[child] += 1

        # Kahn's algorithm for topological sorting
        queue = [t for t in all_topics if in_degree[t] == 0]
        # Sort queue to ensure deterministic sorting order
        queue.sort()

        sorted_path = []

        while queue:
            node = queue.pop(0)
            sorted_path.append(node)

            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
            # Re-sort to maintain alphabetical/deterministic fallback order for nodes of same level
            queue.sort()

        # If a cycle was detected (which shouldn't happen in clean curriculum design),
        # append any missing nodes to ensure no concepts are dropped from the path
        if len(sorted_path) < len(all_topics):
            logger.warning(
                "Cyclic dependencies detected in knowledge graph. Appending remaining items."
            )
            missing = [t for t in all_topics if t not in sorted_path]
            sorted_path.extend(missing)

        return sorted_path

    def evaluate_readiness(
        self,
        topic_id: str,
        prereqs: List[str],
        topic_mastery: Dict[str, float],
        threshold: float = 0.70,
    ) -> bool:
        """
        Checks if the student is ready to study a topic.
        True if and only if all prerequisites have mastery scores >= threshold.
        """
        if not prereqs:
            return True  # No prerequisites implies ready by default

        for p in prereqs:
            if topic_mastery.get(p, 0.0) < threshold:
                return False
        return True
