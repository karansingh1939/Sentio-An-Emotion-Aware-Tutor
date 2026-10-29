import time
import unittest

from fastapi.testclient import TestClient

from sentio.api.app import app
from sentio.intelligence.adaptation import AdaptationEngine
from sentio.intelligence.confidence import ConfidenceEngine
from sentio.intelligence.explanation import ExplanationEngine
from sentio.intelligence.forgetting import ForgettingEngine
from sentio.intelligence.learning_path import LearningPathEngine
from sentio.intelligence.mastery import MasteryEngine
from sentio.intelligence.misconception import MisconceptionEngine
from sentio.intelligence.models import LearnerModel
from sentio.intelligence.progress import ProgressEngine
from sentio.intelligence.recommendation import RecommendationEngine
from sentio.intelligence.session_summary import SessionSummaryEngine
from tests.helpers import login_student


class TestLearningIntelligencePlatform(unittest.TestCase):
    def setUp(self):
        self.mastery = MasteryEngine()
        self.confidence = ConfidenceEngine()
        self.forgetting = ForgettingEngine()
        self.misconception = MisconceptionEngine()
        self.recommendation = RecommendationEngine()
        self.learning_path = LearningPathEngine()
        self.adaptation = AdaptationEngine()
        self.progress = ProgressEngine()
        self.explanation = ExplanationEngine()
        self.summary = SessionSummaryEngine()

    def test_mastery_engine_weight_normalization(self):
        """Verify mastery calculation behaves correctly with missing evidence sources."""
        # 1. All sources present
        quizzes = [{"correct": 1}, {"correct": 0}]  # 50% success
        flashcards = [{"recall_probability": 1.0}, {"recall_probability": None}]
        tutor = [{"learning_state": "engaged"}, {"learning_state": "struggling"}]  # 50% success

        m = self.mastery.calculate_topic_mastery(quizzes, flashcards, tutor)
        expected = 0.5 * 0.5 + 0.3 * 1.0 + 0.2 * 0.5  # 0.25 + 0.30 + 0.10 = 0.65
        self.assertAlmostEqual(m, expected)

        # 2. Only quiz present
        m_quiz_only = self.mastery.calculate_topic_mastery(quizzes, [], [])
        self.assertAlmostEqual(m_quiz_only, 0.5)

    def test_mastery_graph_propagation(self):
        """Verify prerequisite weaknesses scale down downstream mastery estimates."""
        raw_mastery = {"limits": 0.4, "derivatives": 0.8}
        prereqs = {"derivatives": ["limits"]}

        propagated = self.mastery.propagate_mastery(raw_mastery, prereqs)
        # derivatives should be scaled: 0.8 * (0.5 + 0.5 * 0.4) = 0.8 * 0.7 = 0.56
        self.assertAlmostEqual(propagated["derivatives"], 0.56)

    def test_confidence_decay_and_consistency(self):
        """Verify confidence calculation incorporates retention decay and variance."""
        # Baseline confidence
        c1 = self.confidence.calculate_confidence(
            mastery=0.8,
            last_attempt_at=time.time(),
            current_time=time.time(),
            attempts_count=5,
            quiz_scores=[1.0, 1.0, 1.0],
        )
        self.assertTrue(c1 > 0.5)

        # Decay over 10 days
        c2 = self.confidence.calculate_confidence(
            mastery=0.8,
            last_attempt_at=time.time() - (10 * 86400),
            current_time=time.time(),
            attempts_count=5,
            quiz_scores=[1.0, 1.0, 1.0],
        )
        self.assertTrue(c2 < c1)

    def test_forgetting_risk_stability(self):
        """Verify recall risk estimates grow as time elapsed exceeds concept stability."""
        # Highly stable memory
        risk_low, stability_high = self.forgetting.calculate_forgetting_risk(
            last_attempt_at=time.time() - 86400,
            current_time=time.time(),
            repetition_count=5,
            mastery=0.8,
        )
        # Memory decay risk should be very small for 1 day elapsed out of 10 days interval
        self.assertTrue(risk_low < 0.2)

        # High risk memory (decayed over 30 days)
        risk_high, _ = self.forgetting.calculate_forgetting_risk(
            last_attempt_at=time.time() - (30 * 86400),
            current_time=time.time(),
            repetition_count=5,
            mastery=0.8,
        )
        self.assertTrue(risk_high > 0.8)

    def test_misconception_patterns(self):
        """Verify misconception detector tags hint dependence and infinite loops."""
        attempts = [
            {
                "correct": 0,
                "question_text": "recursion tracing",
                "student_answer": "it will run in a loop forever",
            }
        ]
        res = self.misconception.detect_misconceptions(
            topic_id="recursion", quiz_attempts=attempts, hints_requested=5, total_exchanges=10
        )
        # Should flag hint dependency
        self.assertIn("heavy_hint_dependency", res)

    def test_recommendation_prioritization(self):
        """Verify recommendations sort by priority score with clear explanations."""
        recs = self.recommendation.generate_recommendations(
            student_id="stu_test",
            topic_id="recursion",
            mastery=0.3,
            confidence=0.2,
            due_flashcards_count=2,
            has_deck=True,
            prereqs=[],
            prereq_mastery={},
        )
        self.assertTrue(len(recs) > 0)
        # High priority action should be tutoring or flashcards
        self.assertIn(recs[0].action, ("start_tutoring", "review_flashcards"))
        self.assertIn("recursion", recs[0].explanation.lower())

    def test_learning_path_sorting(self):
        """Verify topological sort respects concept prerequisite order."""
        topics = ["derivatives", "limits", "recursion"]
        prereqs = [("limits", "derivatives")]

        path = self.learning_path.sequence_topics(topics, prereqs)
        limits_idx = path.index("limits")
        deriv_idx = path.index("derivatives")
        self.assertTrue(limits_idx < deriv_idx)

    def test_adaptation_parameters(self):
        """Verify tutor adaptation adjusts to low mastery and high cognitive load."""
        model = LearnerModel(student_id="stu_test")
        model.topic_mastery = {"recursion": 0.2}
        model.confidence = {"recursion": 0.1}
        model.cognitive_load_estimate = 0.8

        adj = self.adaptation.compute_adaptation("recursion", model)
        self.assertEqual(adj["difficulty"], "beginner")
        self.assertEqual(adj["pace"], "slow")

    def test_explanation_formatting(self):
        """Verify explanation engine builds structured, readable text strings."""
        details = {"prerequisite": "limits", "prereq_mastery": 0.4}
        text_explanation = self.explanation.explain_recommendation(
            "review_prerequisites", "derivatives", details
        )
        self.assertIn("Limits", text_explanation)
        self.assertIn("40%", text_explanation)

    def test_api_endpoints_mock(self):
        """Verify REST controller routes serve learner profiles and recommendations."""
        from sentio.api.app import PREFIX

        with TestClient(app) as client:
            student_id = login_student(client)
            # Retrieve profile for non-existent student (returns defaulted model)
            resp = client.get(f"{PREFIX}/student/{student_id}/profile")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["student_id"], student_id)

            # Get recommendations
            resp_recs = client.get(f"{PREFIX}/student/{student_id}/recommendations")
            self.assertEqual(resp_recs.status_code, 200)

            # Get learning path
            resp_path = client.get(f"{PREFIX}/student/{student_id}/learning_path")
            self.assertEqual(resp_path.status_code, 200)
            self.assertIn("path", resp_path.json())
